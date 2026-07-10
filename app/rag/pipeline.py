"""
=============================================================================
SmartKrishi - RAG Pipeline
Retrieval-Augmented Generation with ChromaDB + IBM watsonx Embeddings
=============================================================================
"""

import os
import logging
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import chromadb

logger = logging.getLogger(__name__)


# =============================================================================
# RAG CONFIGURATION
# =============================================================================
class RAGConfig:
    CHUNK_SIZE: int = int(os.getenv("RAG_CHUNK_SIZE", 512))
    CHUNK_OVERLAP: int = int(os.getenv("RAG_CHUNK_OVERLAP", 50))
    TOP_K: int = int(os.getenv("RAG_TOP_K", 5))
    SIMILARITY_THRESHOLD: float = float(os.getenv("RAG_SIMILARITY_THRESHOLD", 0.7))
    PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "data/vector_store")
    COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION_NAME", "smartkrishi_knowledge")


# =============================================================================
# KNOWLEDGE BASE DOCUMENTS
# Pre-seeded agricultural knowledge for Indian farming context
# =============================================================================
KNOWLEDGE_BASE_DOCS = [
    # ── Crop Diseases ──────────────────────────────────────────────────────────
    {
        "id": "disease_001",
        "content": """Rice Blast Disease (Magnaporthe oryzae): One of the most devastating rice diseases in India.
Symptoms: Diamond-shaped lesions with gray centers and brown borders on leaves; neck blast causes
panicle breaking at neck. Favorable conditions: High humidity (>90%), temperature 25-28°C, excess nitrogen.
Treatment: Spray Tricyclazole 75 WP @ 0.6g/L or Isoprothiolane 40 EC @ 1.5ml/L. For organic control,
apply Pseudomonas fluorescens @ 2.5 kg/ha. Prevention: Use resistant varieties like IR64, Swarna; avoid
excess nitrogen; maintain proper plant spacing for air circulation. Critical spray timing: at tillering
and panicle initiation stages.""",
        "metadata": {"category": "disease", "crop": "rice", "pathogen_type": "fungal", "region": "all_india"}
    },
    {
        "id": "disease_002",
        "content": """Wheat Rust Diseases (Yellow/Brown/Black Rust): Yellow rust caused by Puccinia striiformis,
brown rust by P. recondita, black rust by P. graminis. Symptoms: Powdery pustules (yellow, brown, or black)
on leaves and stems. Yellow rust appears first in stripes; black rust causes severe stem damage.
Favorable conditions: Cool moist weather for yellow rust; warm moist for brown rust.
Treatment: Propiconazole 25 EC @ 0.1% or Tebuconazole 250 EW @ 0.1%. Apply at first appearance.
Prevention: Sow resistant varieties; follow recommended sowing dates; treat seeds with Carboxin 37.5%
+ Thiram 37.5% WS @ 2g/kg seed. India has rust forecast network — check ICAR-IIWBR alerts.""",
        "metadata": {"category": "disease", "crop": "wheat", "pathogen_type": "fungal", "region": "north_india"}
    },
    {
        "id": "disease_003",
        "content": """Tomato Late Blight (Phytophthora infestans): Highly destructive disease causing crop loss up to 100%.
Symptoms: Water-soaked gray-green spots on leaves that turn brown; white fungal growth on undersides;
dark brown lesions on stem; infected fruits show bronze-brown firm rot.
Favorable conditions: Cool temperatures (10-25°C), high humidity, fog and rain.
Treatment: Mancozeb 75 WP @ 2.5g/L + Cymoxanil 8% WP @ 3g/L (preventive + curative). Metalaxyl-M
+ Mancozeb @ 2.5g/L. Spray at 7-10 day intervals during high-risk weather. Organic: Copper hydroxide
@ 3g/L, Trichoderma viride @ 5g/L soil application. Warning: Do not eat tomatoes within 7 days of
chemical spray (PHI - Pre-Harvest Interval).""",
        "metadata": {"category": "disease", "crop": "tomato", "pathogen_type": "oomycete", "region": "all_india"}
    },
    {
        "id": "disease_004",
        "content": """Cotton Bollworm Complex (Helicoverpa armigera, Pectinophora gossypiella, Earias spp.):
Major pest complex of cotton in India. American bollworm (Helicoverpa) most damaging.
Symptoms: Entry holes in bolls, frass (excreta) around entry points, premature boll opening,
caterpillar inside squares/bolls. Economic threshold: 1 larva per plant or 5-10% damaged bolls.
IPM Approach: 1) Pheromone traps @ 5/acre for monitoring; 2) Release Trichogramma chilonis
@ 50,000/acre at egg stage; 3) Apply NPV (Nuclear Polyhedrosis Virus) @ 250 LE/ha;
4) Spray Bt (Bacillus thuringiensis) var. kurstaki @ 1.5 kg/ha; 5) Chemical: Emamectin benzoate
5 SG @ 0.4g/L only when threshold crossed. Bt cotton hybrids resistant to bollworm — check for
valid Bt technology licenses.""",
        "metadata": {"category": "pest", "crop": "cotton", "pest_type": "lepidoptera", "region": "central_india"}
    },
    {
        "id": "pest_001",
        "content": """Brown Plant Hopper (BPH) - Nilaparvata lugens: Serious pest of rice causing 'hopper burn'.
Symptoms: Yellowing starting from base of tillers, circular patches of dead plants in field (hopperburn),
honeydew secretion attracts sooty mold. BPH transmits Grassy Stunt and Ragged Stunt viruses.
Economic threshold: 10 hoppers per hill. Favorable conditions: High humidity, excessive nitrogen.
Management: 1) Keep bunds clean; 2) Drain field to interrupt BPH feeding; 3) Apply Thiamethoxam 25 WG
@ 0.1g/L or Buprofezin 25 SC @ 1ml/L at base of tillers; 4) Avoid excessive N application.
WARNING: Pyrethroid sprays (Lambda-cyhalothrin, Cypermethrin) cause BPH resurgence — AVOID.
Resistant varieties: IR36, IR64, Swarna Sub1.""",
        "metadata": {"category": "pest", "crop": "rice", "pest_type": "hemiptera", "region": "all_india"}
    },
    # ── Soil & Fertilizers ─────────────────────────────────────────────────────
    {
        "id": "soil_001",
        "content": """Soil pH Management in India: Optimal pH for most crops is 6.0-7.5.
Acidic soils (pH < 5.5) - common in NE India, parts of Jharkhand, Odisha: Apply agricultural lime
(CaCO3) @ 1-4 tonnes/ha based on buffer pH. Reduces aluminum toxicity, improves P availability.
Dolomitic lime (CaMg(CO3)2) better if Mg is also deficient.
Alkaline soils (pH > 8.5) - common in Rajasthan, Punjab, UP: Apply gypsum (CaSO4) @ 4-10 tonnes/ha.
For sodic soils, use pyrite @ 10 tonnes/ha + gypsum. Grow dhaincha (Sesbania) as green manure.
Testing: Soil pH should be tested every 3-5 years. Free testing at ICAR labs and Soil Testing Labs (STL).
Soil Health Card (SHC) scheme: Get your FREE soil health card from agriculture department - tests 12 parameters.""",
        "metadata": {"category": "soil", "topic": "ph_management", "region": "all_india"}
    },
    {
        "id": "soil_002",
        "content": """Nitrogen Management for Kharif Crops: Nitrogen is most yield-limiting nutrient.
Urea (46% N) is most common N source. Split application essential to minimize losses.
Rice nitrogen schedule: 50% as basal (transplanting) + 25% at tillering (21-25 DAT) + 25% at PI stage.
Avoid applying when field is flooded or just before rain. Use neem-coated urea (NCU) — slower release
reduces losses by 10-15%. Rate: 80-120 kg N/ha for hybrid rice, 60-80 kg N/ha for traditional varieties.
Slow-release fertilizers: Sulfur-coated urea, polymer-coated urea for waterlogged conditions.
Biofertilizers: Azospirillum @ 3 packets/ha inoculation on seeds can save 25 kg N/ha.
Blue-green algae (BGA) in paddy fields — apply @ 10 kg/ha in standing water.
Leaf Color Chart (LCC): Free tool distributed by IARI — compare leaf color to determine N top-dressing need.""",
        "metadata": {"category": "soil", "topic": "nitrogen_management", "crop": "rice", "region": "all_india"}
    },
    # ── Government Schemes ────────────────────────────────────────────────────
    {
        "id": "scheme_001",
        "content": """PM-KISAN (Pradhan Mantri Kisan Samman Nidhi): Direct income support scheme for farmers.
Benefit: Rs. 6,000 per year in 3 equal installments of Rs. 2,000 each.
Eligibility: All farmer families (husband, wife, minor children) owning cultivable land.
Exclusion: Institutional landholders, former/current constitutional post holders, serving/retired govt employees
earning >Rs. 10,000/month, IT assessees, professionals like doctors/engineers/lawyers/CAs.
How to Apply: Visit nearest Common Service Centre (CSC) or go to pmkisan.gov.in.
Documents: Aadhaar card, land records (Khasra/Khatauni), bank passbook.
Helpline: 155261 or 011-24300606.
Status Check: pmkisan.gov.in → Farmers Corner → Beneficiary Status (enter Aadhaar/Mobile/Account no)
Latest: eKYC mandatory — do at pmkisan.gov.in or nearest CSC.""",
        "metadata": {"category": "scheme", "scheme_type": "income_support", "ministry": "agriculture"}
    },
    {
        "id": "scheme_002",
        "content": """PM Fasal Bima Yojana (PMFBY) - Pradhan Mantri Fasal Bima Yojana: Crop insurance scheme.
Premium: Kharif crops - 2% of Sum Insured; Rabi crops - 1.5%; Annual commercial/horticultural - 5%.
Coverage: Prevented sowing, standing crop loss (natural calamities, pests, diseases), post-harvest losses
(cyclone, cyclonic rain, unseasonal rain for 14 days after harvest).
Sum Insured: Based on Scale of Finance (cost of cultivation) fixed by district-level committee.
Enrollment: Loanee farmers - automatic through banks (opt-out option available); Non-loanee farmers -
apply through bank/insurance company/CSC/PMFBY portal (pmfby.gov.in) within prescribed cut-off date.
Documents: Land records, bank account, Aadhaar, sowing certificate.
Claim: Report crop loss within 72 hours via Crop Insurance App or call 14447 (toll-free).
Note: States opt in/out — check if your state participates. RWBCIS (Restructured Weather Based Crop Insurance)
available in some states as alternative.""",
        "metadata": {"category": "scheme", "scheme_type": "insurance", "ministry": "agriculture"}
    },
    {
        "id": "scheme_003",
        "content": """Kisan Credit Card (KCC): Revolving credit facility for farmers' agricultural needs.
Credit Limit: Based on scale of finance for crops + 10% post-harvest/household expenses + 20% maintenance
+ consumption credit + 20% crop loan limit for allied activities.
Interest Rate: 7% per annum with 3% interest subvention for timely repayment (effective 4% for prompt payment).
Modified KCC for PM-KISAN beneficiaries: Simplified application — no income certificate needed.
Eligibility: Individual/joint farmers, SHGs, JLGs, tenant farmers, share croppers, oral lessees.
Application: Apply at any Scheduled Commercial Bank, RRB, Cooperative Bank, MFI.
Documents: Land records, identity proof, address proof, passport photo, crop details.
Purpose: Purchase seeds, fertilizers, pesticides, fuel, implements; allied activities (animal husbandry, fisheries).
Repayment: Revolving — repay after harvest and draw again. Valid for 5 years.
Helpline: 1800-180-1551 (Kisan Call Centre)""",
        "metadata": {"category": "scheme", "scheme_type": "credit", "ministry": "finance_agriculture"}
    },
    # ── Crop Calendars ────────────────────────────────────────────────────────
    {
        "id": "crop_calendar_001",
        "content": """Kharif Crop Calendar (June-November) - Major Indian Kharif Crops:
Rice (Paddy): Sow nursery May-June; transplant June-July; harvest September-November. Major states: WB, UP, Punjab, Haryana, Odisha, Bihar, AP, Telangana.
Cotton: Sow May-June (rainfed); harvest October-January. Major: Gujarat, Maharashtra, Telangana, Andhra Pradesh, Rajasthan.
Maize: Sow June-July; harvest September-October. Major: Karnataka, Andhra Pradesh, Maharashtra, Bihar, UP.
Soybean: Sow June-July; harvest September-October. Major: Madhya Pradesh, Maharashtra, Rajasthan.
Groundnut: Sow June-July; harvest October-November. Major: Gujarat, Rajasthan, AP, Tamil Nadu.
Sugarcane: Plant October-November (ratoon); harvest February-April. Major: UP, Maharashtra, Karnataka, TN.
Sorghum (Kharif Jowar): Sow June-July; harvest September-October. Major: Maharashtra, Karnataka.
Pearl Millet (Bajra): Sow June-July; harvest August-September. Major: Rajasthan, Gujarat, Haryana.""",
        "metadata": {"category": "crop_calendar", "season": "kharif", "region": "all_india"}
    },
    {
        "id": "crop_calendar_002",
        "content": """Rabi Crop Calendar (October-March) - Major Indian Rabi Crops:
Wheat: Sow October-December; harvest March-April. Major states: Punjab, Haryana, UP, MP, Bihar, Rajasthan.
  Timely sowing: Nov 1-25 (North India). Varieties: HD-2967, HD-3086, GW-496, PBW-725.
Mustard/Rapeseed: Sow September-October; harvest January-February. Major: Rajasthan, UP, Haryana, MP.
  Varieties: Pusa Bold, NPJ-93, Varuna. Warning: Aphid infestation major problem.
Chickpea (Gram): Sow October-November; harvest February-March. Major: MP, Rajasthan, Maharashtra, Andhra Pradesh.
  Varieties: JG-11, JAKI-9218, Desi vs Kabuli. Wilt and pod borer main challenges.
Lentil (Masoor): Sow October-November; harvest February-March. Major: MP, UP, Bihar, Jharkhand.
Potato: Plant October-December; harvest January-March. Major: UP, West Bengal, Punjab, Bihar, Gujarat.
Sunflower (Rabi): Sow October-November; harvest February-March. Andhra Pradesh, Karnataka.
Peas: Sow October-November; harvest December-February. UP, HP, Punjab, WB, Jharkhand.""",
        "metadata": {"category": "crop_calendar", "season": "rabi", "region": "all_india"}
    },
    # ── Organic Farming ───────────────────────────────────────────────────────
    {
        "id": "organic_001",
        "content": """Vermicompost Production: High-quality organic manure using earthworms (Eisenia fetida).
Setup: Concrete/brick pit (10ft x 4ft x 2ft) or plastic/wooden beds under shade.
Process: 1) Prepare bedding with dry leaves/straw (4 inch layer); 2) Add pre-decomposed farm waste
(cow dung + crop residue 60:40); 3) Maintain moisture (50-60%); 4) Release worms @ 1-2 kg/m²;
5) Cover with jute sacks; 6) Harvest in 45-60 days when material turns dark, crumbly, earthy-smelling.
Nutrient Content: N-1.5-2.5%, P-0.9-1.7%, K-1.5-2.4% + micronutrients + growth hormones.
Application: 2-5 tonnes/ha as basal dose or 100-200g/pit for vegetables.
Economics: Cost Rs. 2-4/kg (self-produced) vs Rs. 10-15/kg market price. 
NABARD subsidy available for vermicompost units — contact district agriculture office.
Certification: For organic export, NPOP certification required from APEDA-accredited certifying agencies.""",
        "metadata": {"category": "organic_farming", "topic": "vermicompost", "region": "all_india"}
    },
    # ── Water Management ──────────────────────────────────────────────────────
    {
        "id": "water_001",
        "content": """Drip Irrigation for Vegetables and Fruits: Saves 30-60% water compared to flood irrigation.
Components: Mainline (63mm HDPE), sub-main (32-63mm), laterals (12-16mm), drippers (2-4 LPH), filter unit, pressure gauge, fertigation tank.
Spacing: For tomato/brinjal/capsicum — lateral spacing 1.2-1.5m, dripper spacing 45-60cm.
For sugarcane — 5 feet between laterals, drippers at 75cm. For orchards (mango/citrus) — 1-2 drippers/tree.
Water Saving: Vegetables: 30-40% saving. Sugarcane: 40-50% saving. Banana: 50-60% saving.
Fertigation: Dissolve water-soluble fertilizers (MKP, potassium nitrate, urea) in injection tank — nutrients delivered to root zone.
Maintenance: Flush system weekly; clean filters monthly; check dripper clogging; acid flushing quarterly.
Subsidy: PM-KRISHI SINCHAYEE YOJANA (PMKSY-PDMC): 45% subsidy for small/marginal farmers; 35% for others.
States have additional subsidy — check PMKSY portal (pmksy.gov.in) or district agriculture office.""",
        "metadata": {"category": "water_management", "topic": "drip_irrigation", "region": "all_india"}
    },
]


def _get_embedding_function():
    """
    Return a ChromaDB-compatible embedding function.
    ChromaDB 1.x ships its own default embeddings (uses onnx models internally).
    We try the sentence-transformers wrapper first; if the optional
    chromadb[sentence-transformers] extra is not installed we fall back to
    ChromaDB's built-in default embedding function.
    """
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        return SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    except Exception:
        # chromadb 1.x default — no extra packages needed
        return chromadb.utils.embedding_functions.DefaultEmbeddingFunction()


# =============================================================================
# VECTOR STORE MANAGER
# =============================================================================
class VectorStoreManager:
    """Manages ChromaDB vector store for RAG pipeline."""

    def __init__(self):
        self.config = RAGConfig()
        self.client: Optional[chromadb.ClientAPI] = None
        self.collection = None
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize ChromaDB client and collection."""
        try:
            persist_dir = Path(self.config.PERSIST_DIR)
            persist_dir.mkdir(parents=True, exist_ok=True)

            # ChromaDB 1.x — Settings import removed; telemetry disabled via env var
            import os as _os
            _os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

            self.client = chromadb.PersistentClient(
                path=str(persist_dir),
            )

            # Embedding function: try chromadb's built-in sentence-transformers wrapper,
            # fall back to chromadb's default (uses its own embedding model).
            embedding_fn = _get_embedding_function()

            self.collection = self.client.get_or_create_collection(
                name=self.config.COLLECTION_NAME,
                embedding_function=embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )

            # Seed with knowledge base if empty
            if self.collection.count() == 0:
                self._seed_knowledge_base()

            self._initialized = True
            logger.info(f"VectorStore initialized with {self.collection.count()} documents")
            return True

        except Exception as e:
            logger.error(f"VectorStore initialization failed: {e}")
            return False

    def _seed_knowledge_base(self):
        """Seed ChromaDB with pre-built agricultural knowledge."""
        if not KNOWLEDGE_BASE_DOCS:
            return

        docs = [d["content"] for d in KNOWLEDGE_BASE_DOCS]
        ids = [d["id"] for d in KNOWLEDGE_BASE_DOCS]
        metadatas = [d["metadata"] for d in KNOWLEDGE_BASE_DOCS]

        # Add in batches of 50
        batch_size = 50
        for i in range(0, len(docs), batch_size):
            self.collection.add(
                documents=docs[i:i + batch_size],
                ids=ids[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size]
            )
        logger.info(f"Seeded {len(docs)} knowledge base documents")

    def add_document(self, doc_id: str, content: str, metadata: dict) -> bool:
        """Add a single document to the vector store."""
        if not self._initialized:
            return False
        try:
            self.collection.add(
                documents=[content],
                ids=[doc_id],
                metadatas=[metadata]
            )
            return True
        except Exception as e:
            logger.error(f"Error adding document {doc_id}: {e}")
            return False

    def add_documents_batch(self, documents: List[Dict]) -> int:
        """Add multiple documents. Returns count of successfully added docs."""
        if not self._initialized:
            return 0
        added = 0
        for doc in documents:
            if self.add_document(doc["id"], doc["content"], doc.get("metadata", {})):
                added += 1
        return added

    def query(
        self,
        query_text: str,
        n_results: int = None,
        filter_metadata: dict = None
    ) -> List[Dict]:
        """
        Query vector store for relevant documents.

        Returns list of {content, metadata, distance, relevance_score}
        """
        if not self._initialized:
            return []

        n_results = n_results or self.config.TOP_K

        try:
            where = filter_metadata if filter_metadata else None
            results = self.collection.query(
                query_texts=[query_text],
                n_results=min(n_results, self.collection.count()),
                where=where,
                include=["documents", "metadatas", "distances"]
            )

            documents = []
            if results and results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0]
                ):
                    # Convert cosine distance to similarity score (0-1)
                    relevance_score = 1 - dist
                    if relevance_score >= self.config.SIMILARITY_THRESHOLD:
                        documents.append({
                            "content": doc,
                            "metadata": meta,
                            "distance": dist,
                            "relevance_score": round(relevance_score, 3)
                        })

            return sorted(documents, key=lambda x: x["relevance_score"], reverse=True)

        except Exception as e:
            logger.error(f"Vector store query error: {e}")
            return []

    def get_stats(self) -> dict:
        """Return collection statistics."""
        if not self._initialized:
            return {"status": "not_initialized"}
        return {
            "status": "ready",
            "document_count": self.collection.count(),
            "collection_name": self.config.COLLECTION_NAME,
            "persist_dir": self.config.PERSIST_DIR
        }

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document from the store."""
        if not self._initialized:
            return False
        try:
            self.collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False


# =============================================================================
# CONTEXT BUILDER
# Formats retrieved documents into a prompt-ready context string
# =============================================================================
class ContextBuilder:
    """Builds formatted context from retrieved documents for LLM prompts."""

    @staticmethod
    def build_context(retrieved_docs: List[Dict], max_tokens: int = 2048) -> str:
        """Build a formatted context string from retrieved documents."""
        if not retrieved_docs:
            return ""

        context_parts = ["=== RELEVANT KNOWLEDGE BASE CONTEXT ===\n"]
        total_chars = 0
        char_limit = max_tokens * 4  # Approximate: 1 token ≈ 4 chars

        for i, doc in enumerate(retrieved_docs, 1):
            meta = doc.get("metadata", {})
            score = doc.get("relevance_score", 0)
            category = meta.get("category", "general").upper()
            crop = meta.get("crop", "")
            region = meta.get("region", "")

            header = f"\n[Context {i} | {category}"
            if crop:
                header += f" | Crop: {crop.title()}"
            if region:
                header += f" | Region: {region.replace('_', ' ').title()}"
            header += f" | Relevance: {score:.0%}]\n"

            entry = header + doc["content"] + "\n"

            if total_chars + len(entry) > char_limit:
                break

            context_parts.append(entry)
            total_chars += len(entry)

        context_parts.append("\n=== END OF CONTEXT ===\n")
        return "".join(context_parts)

    @staticmethod
    def build_augmented_prompt(
        user_query: str,
        context: str,
        conversation_history: List[Dict] = None
    ) -> str:
        """Build the full augmented prompt with context + history + query."""
        parts = []

        if context:
            parts.append(context)

        if conversation_history:
            parts.append("\n=== CONVERSATION HISTORY ===")
            for msg in conversation_history[-6:]:  # Last 3 exchanges
                role = "Farmer" if msg["role"] == "user" else "KrishiMitra"
                parts.append(f"{role}: {msg['content']}")
            parts.append("=== END HISTORY ===\n")

        parts.append(f"Farmer's Question: {user_query}")
        return "\n".join(parts)


# =============================================================================
# DOCUMENT PROCESSOR
# For loading external documents into the knowledge base
# =============================================================================
class DocumentProcessor:
    """Processes external documents and chunks them for the vector store."""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        self.chunk_size = chunk_size or RAGConfig.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or RAGConfig.CHUNK_OVERLAP

    def chunk_text(self, text: str) -> List[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('. ', start, end)
                if last_period > start + self.chunk_size // 2:
                    end = last_period + 1

            chunks.append(text[start:end].strip())
            start = end - self.chunk_overlap

        return [c for c in chunks if c]  # Filter empty chunks

    def process_text_file(
        self,
        file_path: str,
        category: str,
        region: str = "all_india"
    ) -> List[Dict]:
        """Process a text file into document chunks."""
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        chunks = self.chunk_text(text)
        filename = Path(file_path).stem
        timestamp = datetime.utcnow().isoformat()

        return [
            {
                "id": f"{filename}_chunk_{i}_{timestamp}",
                "content": chunk,
                "metadata": {
                    "source": filename,
                    "category": category,
                    "region": region,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "created_at": timestamp
                }
            }
            for i, chunk in enumerate(chunks)
        ]

    def process_json_knowledge(self, json_path: str) -> List[Dict]:
        """Process a JSON file with pre-structured knowledge entries."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "documents" in data:
            return data["documents"]
        return []


# =============================================================================
# SINGLETON INSTANCES (initialized at app startup)
# =============================================================================
vector_store = VectorStoreManager()
context_builder = ContextBuilder()
doc_processor = DocumentProcessor()
