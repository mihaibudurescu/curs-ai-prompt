import json
import os
import hashlib
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import rich
from dotenv import load_dotenv, find_dotenv
import numpy as np
import tensorflow_hub as hub
import tensorflow as tf
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
import faiss

load_dotenv(find_dotenv())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_path_from_base(path_value: str, base_dir: str) -> str:
    """Rezolva path-uri relative fata de folderul curent al agentului."""
    if os.path.isabs(path_value):
        return path_value
    return os.path.abspath(os.path.join(base_dir, path_value))


DATA_DIR = _resolve_path_from_base(os.environ.get("DATA_DIR", "data"), BASE_DIR)
CHUNKS_JSON_PATH = os.path.join(DATA_DIR, "data_chunks.json")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
FAISS_META_PATH = os.path.join(DATA_DIR, "faiss.index.meta")
TRASEE_JSON_PATH = _resolve_path_from_base(
    os.environ.get("TRASEE_JSON_PATH", os.path.join(DATA_DIR, "trasee.json")),
    BASE_DIR,
)

# Fallback util cand DATA_DIR este setat relativ la alt working directory.
DEFAULT_TRASEE_JSON_PATH = os.path.join(BASE_DIR, "data", "trasee.json")
if not os.path.exists(TRASEE_JSON_PATH) and os.path.exists(DEFAULT_TRASEE_JSON_PATH):
    rich.print(
        "[DEBUG] trasee.json nu a fost gasit in DATA_DIR; "
        f"folosesc fallback: {DEFAULT_TRASEE_JSON_PATH}"
    )
    TRASEE_JSON_PATH = DEFAULT_TRASEE_JSON_PATH
USE_MODEL_URL = os.environ.get(
    "USE_MODEL_URL",
    "https://tfhub.dev/google/universal-sentence-encoder/4",
)

WEB_URLS = [u for u in os.environ.get("WEB_URLS", "").split(";") if u]


def _derive_turistmania_zone_base(web_urls: list[str]) -> str:
    """Deriva baza zone-montane din WEB_URLS, cu fallback stabil."""
    explicit = os.environ.get("TURISTMANIA_ZONE_BASE", "").strip()
    if explicit:
        return explicit.rstrip("/")

    for raw_url in web_urls:
        clean = raw_url.strip().rstrip("/")
        if "turistmania.ro" not in clean:
            continue
        if "/ghid-montan/zone-montane" in clean:
            root = clean.split("/ghid-montan/zone-montane", 1)[0]
            return f"{root}/ghid-montan/zone-montane"
        parts = clean.split("/", 3)
        if len(parts) >= 3:
            return f"{parts[0]}//{parts[2]}/ghid-montan/zone-montane"

    return "https://www.turistmania.ro/ghid-montan/zone-montane"


TURISTMANIA_ZONE_BASE = _derive_turistmania_zone_base(WEB_URLS)

class RAGAssistant:
    """Asistent cu RAG din surse web si un LLM pentru raspunsuri."""

    def __init__(self) -> None:
        """Initializeaza clientul LLM, embedderul si prompturile."""
        # Ollama - trebuie sa ruleze local pe http://localhost:11434
        self.client = OpenAI(
            api_key="ollama",  # dummy key pentru Ollama
            base_url="http://localhost:11434/v1"
        )

        os.makedirs(DATA_DIR, exist_ok=True)
        self.embedder = None
        self.zone_chunks_cache: dict[str, list[str]] = {}
        self.turistmania_zone_base = TURISTMANIA_ZONE_BASE
        self.zone_slug_aliases = {
            "fagaras": "fagarasului",
        }

        self.relevance = self._embed_texts(
            "Aceasta este o intrebare despre activitati montane in Romania: ce pot face in Bucegi, Fagaras, Piatra Craiului, trasee, cabane, varfuri, siguranta, echipament si planificarea unei drumetii.",
        )[0]

        self.system_prompt = (
            "Esti un asistent specializat in turismul montan din Romania. "
            "Raspunzi doar la intrebari despre muntii romanesti, trasee turistice, cabane, varfuri, "
            "activitati montane, echipament necesar si sfaturi de siguranta in munte. "
            "Cand utilizatorul intreaba generic (ex: ce activitati poate face intr-un masiv), "
            "ofera intai o sinteza practica (tipuri de activitati, sezonalitate, nivel recomandat, sfaturi), "
            "apoi adauga 3-5 trasee/circuite exemplu cu date concrete. "
            "Cand listezi trasee sau circuite, include pentru fiecare: "
            "numele traseului, localitatea de start, dificultatea, durata si link-ul sursa (sursa_url). "
            "Cand exista date pentru o zona montana (ex: pagina dedicata Turistmania), "
            "include si informatii de context: cai de acces, rezervatii naturale si optiuni de cazare. "
            "Foloseste informatiile din contextul furnizat. Daca nu gasesti informatia in context, "
            "spune ca nu ai date suficiente despre acel subiect. "
            "Raspunde intotdeauna in limba romana, clar si concis."
        )

        self.domain_keywords = {
            "munte", "munti", "montan", "drumetie", "drumetii", "traseu", "trasee",
            "circuit", "circuite", "cabana", "cabane", "varf", "varfuri", "alpina",
            "bucegi", "fagaras", "ceahlau", "parang", "retezat", "pietra", "craiului",
            "ciucas", "sinaia", "busteni", "azuga", "predeal", "brasov", "zarnesti", "activitati",
            "echipament", "siguranta", "salvamont", "campare", "trekking", "hiking", "schi"
        }
        self.known_zone_names = {
            "bucegi", "ciucas", "fagaras", "ceahlau", "retezat", "parang", "apuseni", "giurgeu",
            "harghita", "baiului", "rodnei", "maramuresului", "trascau", "leota",
            "piatra craiului", "postavaru", "iezer papusa", "calimani", "sureanu", "lotrului"
        }


    def _load_documents_from_web(self) -> list[str]:
        """Incarca si chunked documente de pe site-uri prin WebBaseLoader."""
        if os.path.exists(CHUNKS_JSON_PATH):
            try:
                with open(CHUNKS_JSON_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if isinstance(cached, list) and cached:
                    return cached
            except (OSError, json.JSONDecodeError):
                pass

        all_chunks = []
        for url in WEB_URLS:
            try:
                rich.print(f"[DEBUG] Loading {url} ...")
                loader = WebBaseLoader(url)
                docs = loader.load()
                rich.print(f"[DEBUG] Got {len(docs)} doc(s) from {url}")
                for doc in docs:
                    rich.print(f"[DEBUG] Doc content length: {len(doc.page_content)} chars")
                    chunks = self._chunk_text(doc.page_content)
                    rich.print(f"[DEBUG] Chunks produced: {len(chunks)}")
                    all_chunks.extend(chunks)
            except Exception as e:
                rich.print(f"[DEBUG] Failed to load {url}: {e}")
                continue

        rich.print(f"[DEBUG] Total chunks from web: {len(all_chunks)}")

        local_chunks = self._load_from_local_json()
        all_chunks.extend(local_chunks)

        if all_chunks:
            with open(CHUNKS_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(all_chunks, f, ensure_ascii=False)

        return all_chunks

    def _load_from_local_json(self) -> list[str]:
        """Incarca trasee din fisierul JSON local trasee.json."""
        if not os.path.exists(TRASEE_JSON_PATH):
            return []
        try:
            with open(TRASEE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            rich.print(f"[DEBUG] Failed to load local JSON: {e}")
            return []

        trasee = data.get("trasee", []) if isinstance(data, dict) else data
        chunks = []
        for t in trasee:
            if not isinstance(t, dict):
                continue
            parts = []
            if t.get("nume"):
                parts.append(f"Traseu: {t['nume']}")
            if t.get("localitate_start"):
                parts.append(f"Start: {t['localitate_start']}, {t.get('judet', '')}")
            if t.get("dificultate"):
                parts.append(f"Dificultate: {t['dificultate']}")
            if t.get("durata_h"):
                parts.append(f"Durata: {t['durata_h']} ore")
            if t.get("distanta_km"):
                parts.append(f"Distanta: {t['distanta_km']} km")
            if t.get("denivelare_m"):
                parts.append(f"Denivelare: {t['denivelare_m']} m")
            if t.get("sursa_url"):
                parts.append(f"Sursa: {t['sursa_url']}")
            if parts:
                chunks.append("\n".join(parts))
        rich.print(f"[DEBUG] Local JSON chunks: {len(chunks)}")
        return chunks

    def _clean_zone_page_text(self, text: str) -> str:
        """Curata boilerplate-ul frecvent din paginile Turistmania."""
        clean = text or ""
        noise_markers = [
            "Lista comentarii",
            "Trebuie sa fiti logat",
            "Copyrights",
            "ACASA prima pagina",
            "GHID MONTAN",
            "CAUTARE",
            "CONTUL MEU",
            "POSTARI",
        ]
        for marker in noise_markers:
            clean = clean.replace(marker, " ")

        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def _extract_zone_sections(self, text: str) -> list[str]:
        """Extrage sectiuni informative principale pentru context mai bogat."""
        if not text:
            return []

        headings = [
            "Rezervatii naturale",
            "Cai de acces si puncte de pornire la trasee",
            "Trasee turistice in masivul",
            "Unitati de cazare in masivul",
        ]

        sections: list[str] = []
        for heading in headings:
            pattern = rf"{re.escape(heading)}\s*:?\s*(.*?)(?=(Rezervatii naturale|Cai de acces si puncte de pornire la trasee|Trasee turistice in masivul|Unitati de cazare in masivul|Lista comentarii|$))"
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                body = match.group(1).strip()
                if body:
                    sections.append(f"{heading}: {body}")

        if not sections:
            sections.append(text[:3500])

        return sections

    def _normalize_text_for_slug(self, text: str) -> str:
        """Normalizeaza textul pentru detectie zona si slug URL."""
        no_diacritics = unicodedata.normalize("NFD", text)
        no_diacritics = "".join(ch for ch in no_diacritics if unicodedata.category(ch) != "Mn")
        lowered = no_diacritics.lower().strip()
        lowered = re.sub(r"[^a-z0-9\s-]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered

    def _extract_zone_slug(self, user_query: str) -> str | None:
        """Extrage zona montana din intrebare si produce slug-ul pentru URL."""
        normalized = self._normalize_text_for_slug(user_query)

        # Prioritizeaza match-uri curate din lista de zone cunoscute.
        for known_zone in sorted(self.known_zone_names, key=len, reverse=True):
            if re.search(rf"\b{re.escape(known_zone)}\b", normalized):
                return known_zone.replace(" ", "-")

        candidates: list[str] = []
        patterns = [
            r"(?:in|din|zona|muntii|masivul)\s+([a-z0-9\s-]{3,})",
            r"ce\s+pot\s+face\s+in\s+([a-z0-9\s-]{3,})",
            r"ce\s+activitati\s+(?:pot\s+)?(?:face|desfasura)\s+in\s+([a-z0-9\s-]{3,})",
        ]

        for pattern in patterns:
            for match in re.findall(pattern, normalized):
                chunk = match.strip()
                chunk = re.split(r"\b(cu|si|pentru|iarna|vara|toamna|primavara|weekend)\b", chunk)[0].strip()
                # elimina prefixe generice de forma "muntii"/"masivul"
                chunk = re.sub(r"^(muntii|masivul|zona)\s+", "", chunk).strip()
                if chunk:
                    candidates.append(chunk)

        if not candidates:
            return None

        # Prefera candidatul cel mai specific care nu include cuvinte generice.
        best = sorted(candidates, key=lambda c: (len(c.split()), len(c)))[0]
        slug = re.sub(r"\s+", "-", best)
        slug = re.sub(r"-+", "-", slug).strip("-")
        return slug or None

    def _zone_url_exists(self, zone_url: str) -> bool:
        """Verifica existenta URL-ului de zona cu HEAD, apoi fallback GET."""
        req = Request(zone_url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(req, timeout=7) as response:
                status = getattr(response, "status", 200)
                return 200 <= status < 400
        except HTTPError as e:
            if e.code == 405:
                try:
                    get_req = Request(zone_url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(get_req, timeout=7) as response:
                        status = getattr(response, "status", 200)
                        return 200 <= status < 400
                except Exception:
                    return False
            return False
        except URLError:
            return False

    def _zone_page_has_expected_content(self, zone_url: str, zone_slug: str) -> bool:
        """Valideaza ca pagina returnata este chiar pagina masivului, nu o pagina generica."""
        try:
            req = Request(zone_url, method="GET", headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(req, timeout=7) as response:
                html = response.read().decode("utf-8", errors="ignore")
        except Exception:
            return False

        normalized = self._normalize_text_for_slug(html)
        normalized_slug = zone_slug.replace("-", " ")
        slug_markers = [normalized_slug]
        if not normalized_slug.endswith("ului"):
            slug_markers.append(normalized_slug + "ului")
        if not normalized_slug.endswith("lui"):
            slug_markers.append(normalized_slug + "lui")

        has_zone_marker = any(
            ("muntii " + marker) in normalized or ("masivul " + marker) in normalized
            for marker in slug_markers
        )
        has_structure_marker = (
            "trasee turistice" in normalized
            and ("unitati de cazare" in normalized or "cai de acces" in normalized)
        )
        return has_zone_marker and has_structure_marker

    def _resolve_zone_url(self, zone_slug: str) -> tuple[str, str] | tuple[None, None]:
        """Rezolva URL-ul unei zone, inclusiv variante cu sufixe romanesti frecvente."""
        base_slug = zone_slug.strip("-")
        candidate_slugs = []

        explicit_alias = self.zone_slug_aliases.get(base_slug)
        if explicit_alias:
            candidate_slugs.append(explicit_alias)

        candidate_slugs.append(base_slug)

        if not base_slug.endswith("ului"):
            candidate_slugs.append(base_slug + "ului")
        if not base_slug.endswith("lui"):
            candidate_slugs.append(base_slug + "lui")

        seen: set[str] = set()
        for candidate_slug in candidate_slugs:
            if candidate_slug in seen:
                continue
            seen.add(candidate_slug)

            zone_url = f"{self.turistmania_zone_base.rstrip('/')}/{candidate_slug}.html"
            if self._zone_page_has_expected_content(zone_url, candidate_slug):
                if candidate_slug != zone_slug:
                    rich.print(f"[DEBUG] Zone URL fallback: {zone_slug} -> {candidate_slug}")
                return candidate_slug, zone_url

        return None, None

    def _load_dynamic_zone_chunks(self, user_query: str) -> list[str]:
        """Incarca chunks din pagina Turistmania aferenta zonei detectate."""
        zone_slug = self._extract_zone_slug(user_query)
        if not zone_slug:
            return []

        if zone_slug in self.zone_chunks_cache:
            return self.zone_chunks_cache[zone_slug]

        resolved_slug, zone_url = self._resolve_zone_url(zone_slug)
        if not zone_url or not resolved_slug:
            rich.print(f"[DEBUG] Zone page missing for slug: {zone_slug}")
            self.zone_chunks_cache[zone_slug] = []
            return []

        try:
            rich.print(f"[DEBUG] Loading dynamic zone page: {zone_url}")
            docs = WebBaseLoader(zone_url).load()
        except Exception as e:
            rich.print(f"[DEBUG] Failed dynamic zone load {zone_url}: {e}")
            self.zone_chunks_cache[zone_slug] = []
            return []

        zone_chunks: list[str] = []
        for doc in docs:
            raw_text = (doc.page_content or "").strip()
            if not raw_text:
                continue
            cleaned = self._clean_zone_page_text(raw_text)
            for section in self._extract_zone_sections(cleaned):
                # Chunk-uri mai mari pastreaza coeziunea detaliilor despre trasee/rezervatii.
                for chunk in self._chunk_text(section, chunk_size=900, chunk_overlap=120):
                    zone_chunks.append(f"Sursa: {zone_url}\nZona: {resolved_slug}\n{chunk}")

        rich.print(f"[DEBUG] Dynamic zone chunks ({zone_slug}): {len(zone_chunks)}")
        self.zone_chunks_cache[zone_slug] = zone_chunks
        return zone_chunks

    def _send_prompt_to_llm(
        self,
        user_input: str,
        context: str
    ) -> str:
        """Trimite promptul catre LLM si returneaza raspunsul."""

        system_msg = self.system_prompt

        activity_intent = self._is_activity_intent(user_input)
        if activity_intent:
            user_task = (
                "Raspunde cu o structura in 3 sectiuni: "
                "(1) Activitati recomandate in zona ceruta, "
                "(2) Trasee/circuite exemplu (3-5) cu dificultate, durata si sursa_url, "
                "(3) Sfaturi de siguranta si echipament de baza."
            )
        else:
            user_task = (
                "Raspunde la intrebare folosind contextul si include pentru fiecare traseu mentionat "
                "link-ul sursa (sursa_url)."
            )

        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": (
                    f"Folosind urmatorul context despre turismul montan din Romania:\n\n{context}\n\n"
                    f"{user_task}\n"
                    f"Intrebarea utilizatorului: {user_input}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model="mistral",  # sau llama2, neural-chat, etc.
            )
            return response.choices[0].message.content
        except Exception as e:
            rich.print(f"[DEBUG] LLM error: {e}")
            return (
                "Asistent: Nu pot ajunge la Ollama. Asigura-te ca Ollama ruleaza local cu 'ollama serve'. "
                "Te rog incearca din nou in cateva momente."
            )
        
    def _embed_texts(self, texts: str | list[str], batch_size: int = 32) -> np.ndarray:
        """Genereaza embeddings folosind Universal Sentence Encoder."""
        if isinstance(texts, str):
            texts = [texts]
        if self.embedder is None:
            self.embedder = hub.load(USE_MODEL_URL)
        if callable(self.embedder):
            embeddings = self.embedder(texts)
        else:
            infer = self.embedder.signatures.get("default")
            if infer is None:
                raise ValueError("Model USE nu expune semnatura 'default'.")
            outputs = infer(tf.constant(texts))
            embeddings = outputs.get("default")
            if embeddings is None:
                raise ValueError("Model USE nu a returnat cheia 'default'.")
        return np.asarray(embeddings, dtype="float32")

    def _chunk_text(self, text: str, chunk_size: int = 300, chunk_overlap: int = 20) -> list[str]:
        """Imparte textul in bucati cu RecursiveCharacterTextSplitter."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        chunks = splitter.split_text(text or "")
        return chunks if chunks else [""]

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculeaza similaritatea cosine intre doi vectori."""
        denom = (np.linalg.norm(a) * np.linalg.norm(b))
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    def _build_faiss_index_from_chunks(self, chunks: list[str]) -> faiss.IndexFlatIP:
        """Construieste index FAISS din chunks text si il salveaza pe disc."""
        if not chunks:
            raise ValueError("Lista de chunks este goala.")

        embeddings = self._embed_texts(chunks).astype("float32")
        faiss.normalize_L2(embeddings)

        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings)
        faiss.write_index(index, FAISS_INDEX_PATH)
        with open(FAISS_META_PATH, "w", encoding="utf-8") as f:
            f.write(self._compute_chunks_hash(chunks))
        return index

    def _compute_chunks_hash(self, chunks: list[str]) -> str:
        """Hash determinist pentru lista de chunks si model."""
        payload = json.dumps(
            {
                "model": USE_MODEL_URL,
                "chunks": chunks,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _load_index_hash(self) -> str | None:
        """Incarca hash-ul asociat indexului FAISS."""
        if not os.path.exists(FAISS_META_PATH):
            return None
        try:
            with open(FAISS_META_PATH, "r", encoding="utf-8") as f:
                return f.read().strip()
        except OSError:
            return None

    def _retrieve_relevant_chunks(self, chunks: list[str], user_query: str, k: int = 5) -> list[str]:
        """Rankeaza chunks folosind FAISS si returneaza top-k relevante."""
        if not chunks:
            return []

        current_hash = self._compute_chunks_hash(chunks)
        stored_hash = self._load_index_hash()

        query_embedding = self._embed_texts(user_query).astype("float32")

        index = None
        if os.path.exists(FAISS_INDEX_PATH) and stored_hash == current_hash:
            try:
                index = faiss.read_index(FAISS_INDEX_PATH)
                if index.ntotal != len(chunks) or index.d != query_embedding.shape[1]:
                    index = None
            except Exception:
                index = None

        if index is None:
            index = self._build_faiss_index_from_chunks(chunks)

        faiss.normalize_L2(query_embedding)

        k = min(k, len(chunks))
        if k == 0:
            return []

        _, indices = index.search(query_embedding, k=k)
        return [chunks[i] for i in indices[0] if i < len(chunks)]

    def _retrieve_by_locality(self, user_query: str) -> list[str]:
        """Cauta direct in trasee.json dupa localitate_start sau nume traseu."""
        if not os.path.exists(TRASEE_JSON_PATH):
            return []
        try:
            with open(TRASEE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        trasee = data.get("trasee", []) if isinstance(data, dict) else data
        query_lower = user_query.lower()
        # strip punctuation and extract words (min 4 chars)
        clean = "".join(c if c.isalpha() or c.isspace() else " " for c in query_lower)
        keywords = [w for w in clean.split() if len(w) >= 4]
        rich.print(f"[DEBUG] Locality keywords: {keywords}")

        matched = []
        for t in trasee:
            localitate = (t.get("localitate_start") or "").lower()
            judet = (t.get("judet") or "").lower()
            # match only against localitate_start and judet, not sursa_url or nume
            # to avoid false positives from generic words like "montane"
            if any(kw in localitate or kw in judet for kw in keywords):
                parts = []
                if t.get("nume"):
                    parts.append(f"Traseu: {t['nume']}")
                if t.get("localitate_start"):
                    parts.append(f"Start: {t['localitate_start']}, {t.get('judet', '')}")
                if t.get("dificultate"):
                    parts.append(f"Dificultate: {t['dificultate']}")
                if t.get("durata_h"):
                    parts.append(f"Durata: {t['durata_h']} ore")
                if t.get("distanta_km"):
                    parts.append(f"Distanta: {t['distanta_km']} km")
                if t.get("denivelare_m"):
                    parts.append(f"Denivelare: {t['denivelare_m']} m")
                if t.get("sursa_url"):
                    parts.append(f"Sursa: {t['sursa_url']}")
                if parts:
                    matched.append("\n".join(parts))
        rich.print(f"[DEBUG] Locality match chunks: {len(matched)}")
        return matched

    def _contains_domain_keywords(self, user_input: str) -> bool:
        """Fallback lexical pentru intrebari montane formulate generic."""
        query_lower = user_input.lower()
        clean = "".join(c if c.isalpha() or c.isspace() else " " for c in query_lower)
        tokens = set(clean.split())
        if not tokens:
            return False

        if tokens.intersection(self.domain_keywords):
            return True

        joined = " ".join(tokens)
        multi_word_markers = ["ce pot face", "in munti", "in bucegi", "la munte"]
        return any(marker in query_lower or marker in joined for marker in multi_word_markers)

    def _is_activity_intent(self, user_input: str) -> bool:
        """Detecteaza intentia de recomandari generale de activitati."""
        query = user_input.lower()
        markers = [
            "ce activitati", "ce pot face", "activitati", "ce pot desfasura",
            "ce sa fac", "recomandari", "weekend in", "ce fac in"
        ]
        return any(marker in query for marker in markers)

    def _is_zone_query(self, user_input: str) -> str | None:
        """Returneaza slug-ul masivului daca intrebarea vizeaza o zona montana cunoscuta."""
        normalized = self._normalize_text_for_slug(user_input)
        for known_zone in sorted(self.known_zone_names, key=len, reverse=True):
            if re.search(r"\b" + re.escape(known_zone) + r"\b", normalized):
                return known_zone.replace(" ", "-")
        return None

    def _retrieve_from_json_by_zone(self, zone_slug: str) -> list[str]:
        """Cauta trasee in trasee.json unde zona apare in campul 'nume'."""
        if not os.path.exists(TRASEE_JSON_PATH):
            return []
        try:
            with open(TRASEE_JSON_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []

        trasee = data.get("trasee", []) if isinstance(data, dict) else data
        zone_norm = self._normalize_text_for_slug(zone_slug.replace("-", " "))

        matched = []
        for t in trasee:
            if not isinstance(t, dict):
                continue
            candidate = self._normalize_text_for_slug(
                (t.get("nume") or "") + " " + (t.get("localitate_start") or "")
            )
            if zone_norm in candidate:
                parts = []
                if t.get("nume"):
                    parts.append("Traseu: " + t["nume"])
                if t.get("localitate_start"):
                    parts.append("Start: " + t["localitate_start"] + ", " + t.get("judet", ""))
                if t.get("dificultate"):
                    parts.append("Dificultate: " + t["dificultate"])
                if t.get("durata_h"):
                    parts.append("Durata: " + str(t["durata_h"]) + " ore")
                if t.get("distanta_km"):
                    parts.append("Distanta: " + str(t["distanta_km"]) + " km")
                if t.get("denivelare_m"):
                    parts.append("Denivelare: " + str(t["denivelare_m"]) + " m")
                if t.get("sursa_url"):
                    parts.append("Sursa: " + t["sursa_url"])
                if parts:
                    matched.append("\n".join(parts))

        rich.print("[DEBUG] JSON by zone (" + zone_slug + "): " + str(len(matched)) + " trasee")
        return matched[:5]

    def _extract_structured_zone_data(self, text: str) -> dict[str, str]:
        """Extrage date structurate din textul paginii Turistmania a unei zone."""
        boundary = (
            "(?:Localizare, intindere, limite|Rezervatii naturale|Clima|Flora si fauna"
            "|Rauri si lacuri|Cai de acces[^:]*|Trasee turistice(?: in masivul\\s+\\w+)?"
            "|Unitati de cazare in (?:masivul|muntii)\\s+[a-z\\s-]+|Lista comentarii)"
        )
        result: dict[str, str] = {}

        localizare_match = re.search(
            "(?:Localizare, intindere, limite)\\s*:?\\s*(.*?)(?=" + boundary + "|$)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if localizare_match:
            body = re.sub("\\s+", " ", localizare_match.group(1)).strip()
            if body:
                result["situare"] = body[:1800]
        else:
            first_heading = re.search(boundary, text, flags=re.IGNORECASE)
            if first_heading:
                intro = text[: first_heading.start()].strip()
                if intro:
                    result["situare"] = intro[:1500]

        for key, heading_pat in [
            ("rezervatii", "Rezervatii naturale"),
            ("trasee", "Trasee turistice(?: in masivul\\s+\\w+)?"),
            ("cazare", "Unitati de cazare in (?:masivul|muntii)\\s+[a-z\\s-]+"),
        ]:
            pattern = "(?:" + heading_pat + ")\\s*:?\\s*(.*?)(?=" + boundary + "|$)"
            match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
            if match:
                body = re.sub("\\s+", " ", match.group(1)).strip()
                if body:
                    result[key] = body

        access_matches = re.findall(
            "(?:Cai de acces[^:]*)\\s*:?\\s*(.*?)(?=" + boundary + "|$)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if access_matches:
            access_sections = []
            for match in access_matches:
                body = re.sub("\\s+", " ", match).strip()
                if body:
                    access_sections.append(body)
            if access_sections:
                result["acces"] = " ".join(access_sections)

        return result

    def _zone_structured_response(self, zone_slug: str, zone_url: str, user_message: str) -> str:
        """Genereaza raspuns structurat pentru o zona montana, cu sursa primara Turistmania."""
        zone_display = zone_slug.replace("-", " ").title()

        zone_data: dict[str, str] = {}
        try:
            rich.print("[DEBUG] Zone structured load: " + zone_url)
            docs = WebBaseLoader(zone_url).load()
            for doc in docs:
                raw = (doc.page_content or "").strip()
                if raw:
                    cleaned = self._clean_zone_page_text(raw)
                    zone_data = self._extract_structured_zone_data(cleaned)
                    break
        except Exception as e:
            rich.print("[DEBUG] Zone structured load failed: " + str(e))

        json_trasee = self._retrieve_from_json_by_zone(zone_slug)

        context_parts: list[str] = [
            "=== DATE DESPRE MUNTII " + zone_display.upper() + " ===",
            "Sursa principala: " + zone_url,
        ]
        if zone_data.get("situare"):
            context_parts += ["", "[SITUARE]", zone_data["situare"]]
        if zone_data.get("rezervatii"):
            context_parts += ["", "[REZERVATII NATURALE]", zone_data["rezervatii"][:1200]]
        if zone_data.get("acces"):
            context_parts += ["", "[CAI DE ACCES]", zone_data["acces"][:1200]]
        if zone_data.get("trasee"):
            context_parts += ["", "[TRASEE TURISTICE - sursa Turistmania]", zone_data["trasee"][:2500]]
        if json_trasee:
            context_parts += ["", "[TRASEE SUPLIMENTARE - sursa trasee.json]"] + json_trasee
        if zone_data.get("cazare"):
            context_parts += ["", "[CAZARE]", zone_data["cazare"][:500]]

        context = "\n".join(context_parts)

        prompt_lines = [
            "Folosind EXCLUSIV datele de mai jos despre Muntii " + zone_display + ":",
            "",
            context,
            "",
            "Genereaza un raspuns structurat cu exact urmatoarele sectiuni:",
            "## 1. Situarea muntilor",
            "## 2. Rezervatii naturale",
            "## 3. Cai de acces",
            "## 4. Trasee turistice (exact 5 trasee cu: nume, marcaj daca exista, durata, dificultate, sursa)",
            "## 5. Cazare",
            "",
            "IMPORTANT:",
            "- Foloseste DOAR informatiile din contextul de mai sus.",
            "- Nu mentiona alte zone montane.",
            "- La sectiunea Trasee, prioritizeaza datele din [TRASEE TURISTICE - sursa Turistmania],"
            " completeaza cu [TRASEE SUPLIMENTARE - sursa trasee.json] daca e nevoie pentru a ajunge la 5.",
            "- Raspunde in limba romana.",
            "Intrebarea utilizatorului: " + user_message,
        ]
        zone_prompt = "\n".join(prompt_lines)

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": zone_prompt},
        ]
        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model="mistral",  # sau llama2, neural-chat, etc.
            )
            return response.choices[0].message.content
        except Exception as e:
            rich.print("[DEBUG] LLM zone error: " + str(e))
            return "Asistent: Nu pot ajunge la Ollama. Asigura-te ca 'ollama serve' ruleaza local."

    def calculate_similarity(self, text: str) -> float:
        """Returneaza similaritatea cu propozitia de referinta a domeniului montan."""
        embedding = self._embed_texts(text.strip())[0]
        return self._cosine_similarity(embedding, self.relevance)

    def is_relevant(self, user_input: str) -> bool:
        """Permite intrebari montane prin semantica + fallback lexical."""
        semantic_ok = self.calculate_similarity(user_input) >= 0.42
        lexical_ok = self._contains_domain_keywords(user_input)
        return semantic_ok or lexical_ok

    def assistant_response(self, user_message: str) -> str:
        """Directioneaza mesajul utilizatorului catre calea potrivita."""
        if not user_message:
            return "Te rog scrie o intrebare despre turismul montan din Romania. Exemplu: 'Care sunt cele mai frumoase trasee din Bucegi?'"

        if not self.is_relevant(user_message):
            return (
                "Intrebarea ta nu pare a fi despre turismul montan din Romania. "
                "Te rog intreaba despre trasee, cabane, varfuri sau activitati in muntii romanesti. "
                "Exemplu: 'Ce echipament am nevoie pentru Fagaras?'"
            )

        # Daca intrebarea vizeaza un masiv montan cunoscut → raspuns structurat cu sursa Turistmania
        zone_slug = self._is_zone_query(user_message)
        if zone_slug:
            _, zone_url = self._resolve_zone_url(zone_slug)
            if zone_url:
                return self._zone_structured_response(zone_slug, zone_url, user_message)

        # Altfel: RAG general din web cache + JSON
        chunks = self._load_documents_from_web()
        relevant_chunks = self._retrieve_relevant_chunks(chunks, user_message, k=18)
        locality_chunks = self._retrieve_by_locality(user_message)
        if self._is_activity_intent(user_message):
            locality_chunks = locality_chunks[:5]
            relevant_chunks = relevant_chunks[:14]
        seen = set()
        combined = []
        for c in locality_chunks + relevant_chunks:
            if c not in seen:
                seen.add(c)
                combined.append(c)
        context = "\n\n".join(combined)
        return self._send_prompt_to_llm(user_message, context)

if __name__ == "__main__":
    assistant = RAGAssistant()
    rich.print("[bold green]=== Test localitate ===[/bold green]")
    rich.print(assistant.assistant_response("Care sunt circuitele montane posibile din localitatea Busteni?"))  # test localitate
    
    rich.print("[bold green]=== Test zona structurata ===[/bold green]")
    rich.print(assistant.assistant_response("Ce activitati pot desfasura in muntii Ciucas?"))  # test zona structurata
    rich.print(assistant.assistant_response("Ce pot face in muntii Fagaras?"))  # test zona structurata
    
    rich.print("[yellow]Warning:[/yellow] Testul irelevant")
    rich.print(assistant.assistant_response("Care este reteta de sarmale?"))  # test irelevant