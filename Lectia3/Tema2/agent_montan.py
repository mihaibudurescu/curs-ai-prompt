import json
import os
import hashlib

from dotenv import load_dotenv, find_dotenv
import numpy as np
import tensorflow_hub as hub
import tensorflow as tf
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import OpenAI
import faiss

load_dotenv(find_dotenv())

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
CHUNKS_JSON_PATH = os.path.join(DATA_DIR, "data_chunks.json")
FAISS_INDEX_PATH = os.path.join(DATA_DIR, "faiss.index")
FAISS_META_PATH = os.path.join(DATA_DIR, "faiss.index.meta")
TRASEE_JSON_PATH = os.path.join(DATA_DIR, "trasee.json")
USE_MODEL_URL = os.environ.get(
    "USE_MODEL_URL",
    "https://tfhub.dev/google/universal-sentence-encoder/4",
)

WEB_URLS = [u for u in os.environ.get("WEB_URLS", "").split(";") if u]

class RAGAssistant:
    """Asistent cu RAG din surse web si un LLM pentru raspunsuri."""

    def __init__(self) -> None:
        """Initializeaza clientul LLM, embedderul si prompturile."""
        self.groq_api_key = os.environ.get("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("Seteaza GROQ_API_KEY in variabilele de mediu.")

        self.client = OpenAI(
            api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1"
        )

        os.makedirs(DATA_DIR, exist_ok=True)
        self.embedder = None

        # ToDo: Adaugat o propozitie de referinta mai specifica pentru domeniul dvs
        self.relevance = self._embed_texts(
            "Aceasta este o intrebare despre turism montan in Romania, trasee, cabane, varfuri sau activitati in muntii romanesti.",
        )[0]

        # ToDo: Definiti un prompt de sistem mai detaliat pentru a ghida raspunsurile LLM-ului in directia dorita
        self.system_prompt = (
            "Esti un asistent specializat in turismul montan din Romania. "
            "Raspunzi doar la intrebari despre muntii romanesti, trasee turistice, cabane, varfuri, "
            "activitati montane, echipament necesar si sfaturi de siguranta in munte. "
            "Cand listezi trasee sau circuite, include intotdeauna pentru fiecare: "
            "numele traseului, localitatea de start, dificultatea, durata si link-ul sursa (sursa_url). "
            "Foloseste informatiile din contextul furnizat. Daca nu gasesti informatia in context, "
            "spune ca nu ai date suficiente despre acel subiect. "
            "Raspunde intotdeauna in limba romana, clar si concis."
        )


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
                print(f"[DEBUG] Loading {url} ...")
                loader = WebBaseLoader(url)
                docs = loader.load()
                print(f"[DEBUG] Got {len(docs)} doc(s) from {url}")
                for doc in docs:
                    print(f"[DEBUG] Doc content length: {len(doc.page_content)} chars")
                    chunks = self._chunk_text(doc.page_content)
                    print(f"[DEBUG] Chunks produced: {len(chunks)}")
                    all_chunks.extend(chunks)
            except Exception as e:
                print(f"[DEBUG] Failed to load {url}: {e}")
                continue

        print(f"[DEBUG] Total chunks from web: {len(all_chunks)}")

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
            print(f"[DEBUG] Failed to load local JSON: {e}")
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
        print(f"[DEBUG] Local JSON chunks: {len(chunks)}")
        return chunks

    def _send_prompt_to_llm(
        self,
        user_input: str,
        context: str
    ) -> str:
        """Trimite promptul catre LLM si returneaza raspunsul."""

        system_msg = self.system_prompt

        # ToDo: Ajustati acest prompt pentru a se potrivi mai bine cu domeniul dvs si pentru a ghida LLM-ul sa ofere raspunsuri mai relevante si structurate.
        messages = [
            {"role": "system", "content": system_msg},
            {
                "role": "user",
                "content": (
                    f"Folosind urmatorul context despre turismul montan din Romania:\n\n{context}\n\n"
                    f"Raspunde la urmatoarea intrebare si include pentru fiecare traseu mentionat link-ul sursa (sursa_url): {user_input}"
                ),
            },
        ]

        try:
            response = self.client.chat.completions.create(
                messages=messages,
                model="llama-3.3-70b-versatile",
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[DEBUG] LLM error: {e}")
            return (
                "Asistent: Nu pot ajunge la modelul de limbaj acum. "
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

    def _chunk_text(self, text: str) -> list[str]:
        """Imparte textul in bucati cu RecursiveCharacterTextSplitter."""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=20,
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
        print(f"[DEBUG] Locality keywords: {keywords}")

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
        print(f"[DEBUG] Locality match chunks: {len(matched)}")
        return matched

    def calculate_similarity(self, text: str) -> float:
        # ToDo: Ajustati aceasta propozitie de referinta pentru a se potrivi mai bine cu domeniul dvs, astfel incat sa reflecte mai precis ce inseamna "relevant" in contextul aplicatiei dvs.
        """Returneaza similaritatea cu o propozitie de referinta despre ... ."""
        embedding = self._embed_texts(text.strip())[0]
        return self._cosine_similarity(embedding, self.relevance)

    def is_relevant(self, user_input: str) -> bool:
        # ToDo: Ajustati pragul de similaritate pentru a se potrivi mai bine cu domeniul dvs, astfel incat sa echilibreze corect intre a permite intrebari relevante si a respinge cele irelevante.
        """Verifica daca intrarea utilizatorului e despre ...."""
        return self.calculate_similarity(user_input) >= 0.5

    def assistant_response(self, user_message: str) -> str:
        """Directioneaza mesajul utilizatorului catre calea potrivita."""
        if not user_message:
            # ToDo: Ajustati acest mesaj pentru a fi mai specific pentru domeniul dvs, astfel incat sa ghideze utilizatorii sa puna intrebari relevante si sa ofere un exemplu concret.
            return "Te rog scrie o intrebare despre turismul montan din Romania. Exemplu: 'Care sunt cele mai frumoase trasee din Bucegi?'"

        if not self.is_relevant(user_message):
            # ToDo: Ajustati acest mesaj pentru a fi mai specific pentru domeniul dvs, astfel incat sa ghideze utilizatorii sa puna intrebari relevante si sa ofere un exemplu concret.
            return (
                "Intrebarea ta nu pare a fi despre turismul montan din Romania. "
                "Te rog intreaba despre trasee, cabane, varfuri sau activitati in muntii romanesti. "
                "Exemplu: 'Ce echipament am nevoie pentru Fagaras?'"
            )

        chunks = self._load_documents_from_web()
        relevant_chunks = self._retrieve_relevant_chunks(chunks, user_message, k=15)
        locality_chunks = self._retrieve_by_locality(user_message)
        # merge, deduplicate, locality matches first
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
    # ToDo: Testati cu intrebari relevante pentru domeniul dvs, precum si cu intrebari irelevante pentru a va asigura ca logica de filtrare functioneaza corect.
    print(assistant.assistant_response("Care sunt circuitele montane posibile din localitatea Busteni?"))  # test relevant
    print(assistant.assistant_response("Care este reteta de sarmale?"))  # test irelevant