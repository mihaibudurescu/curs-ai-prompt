# importă bibliotecile necesare
import os
from langchain_groq import ChatGroq
from langchain.agents import load_tools
from langchain.agents import initialize_agent
from langchain.tools import tool
from dotenv import load_dotenv

load_dotenv()

# încarcă cheile API din variabilele de mediu
os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY")
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

# initializarea modelului de limbaj și alegerea uneltelor
llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

@tool
def year_power(year: str) -> float:
    """Raises a year number to the power of 0.23 and returns the result."""
    return float(year) ** 0.23

tools = load_tools(["google-serper"], llm=llm) + [year_power]

# initializarea agentului cu uneltele și modelul de limbaj
agent = initialize_agent(tools, llm, agent="zero-shot-react-description", verbose=True)

# rularea agentului cu o întrebare specifică și afișarea răspunsului
response = agent.run(
    "Find the big event and the year Alexandru Ioan Cuza has done during his life. "
    "Then use the year_power tool to calculate year^0.23. "
    "Reply exactly as: event=<name>; year=<number>; year^0.23=<result>"
)

print(response)