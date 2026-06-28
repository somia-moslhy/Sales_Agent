from dataclasses import dataclass, field
from typing import List, Optional
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from database.mongodb import MongoDBHandler

load_dotenv()

# =========================
# Langfuse Observability 
# =========================
if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
    try:
        from langfuse import get_client
        langfuse = get_client()
        Agent.instrument_all()
        print("✅ تم تفعيل تتبع Langfuse لمحادثات الوكيل.")
    except Exception as e:
        print(f"⚠️  تعذّر تفعيل تتبع Langfuse (سيستمر التطبيق بدون تتبع): {e}")

# =========================
# Usage Limits
# =========================
KAYFA_TURN_USAGE_LIMITS = UsageLimits(request_limit=2)

# =========================
# Pricing & Free Content Files 
# =========================
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PRICING_FILES = {
    "individual": _DATA_DIR / "kayfa_paid_individual_courses.md",
    "tracks":     _DATA_DIR / "kayfa_paid_educational_tracks.md",
    "free":       _DATA_DIR / "kayfa_free_educational_content.md", 
    }

def _load_pricing_context() -> str:
    parts = []
    for label, path in _PRICING_FILES.items():
        if path.exists():
            try:
                parts.append(f"--- {path.name} ---\n{path.read_text(encoding='utf-8')}")
            except Exception:
                pass   
    return "\n\n".join(parts)

_PRICE_KEYWORDS = {
    # Arabic
    "سعر", "أسعار", "تكلفة", "تكاليف", "بكام", "بكم", "كام", "كم",
    "رسوم", "اشتري", "أشتري", "دفع", "أدفع", "تقسيط", 
    "مجاني", "مجانا", "مجاناً", "بلاش", "هدية", # 
    # English
    "price", "pricing", "cost", "fee", "fees", "how much", "cheap",
    "expensive", "affordable", "pay", "payment", "buy", "purchase", 
    "free", 
}

def _is_price_query(query: str) -> bool:
    q_lower = query.lower()
    return any(kw in q_lower for kw in _PRICE_KEYWORDS)

# =========================
# CRM Ticket Schema
# =========================
class CRMTicket(BaseModel):
    name: str             = Field(..., description="Potential customer name")
    phone: str            = Field(..., description="Contact number (WhatsApp or Phone)")
    email: Optional[str]  = Field(None, description="Email address if available")
    location: str         = Field(..., description="City and Country (e.g., Cairo, Egypt)")
    language_dialect: str = Field(default="Arabic", description="Preferred language and dialect")
    interested_products: List[str] = Field(..., description="Products of interest (courses or diplomas)")
    
    # We provided default values and explicitly prevented asking the customer
    goal: str             = Field(default="تطوير المهارات", description="Goal for learning. INFER THIS. DO NOT ASK THE USER.")
    current_level: str    = Field(default="غير محدد", description="Current technical level. INFER THIS. DO NOT ASK THE USER.")
    lead_temperature: str = Field(default="Warm", description="Lead seriousness: Hot/Warm/Cold. GUESS THIS. NEVER ASK THE USER.")
    objections: Optional[str] = Field(default="لا يوجد", description="Any objections raised. INFER THIS. DO NOT ASK.")
    
    conversation_summary: str = Field(..., description="Short Arabic summary of the conversation")
    next_action: str      = Field(default="التواصل مع العميل", description="Recommended next action for the sales rep")
    timestamp: str        = Field(..., description="Ticket creation time — YYYY-MM-DD HH:MM format")

    @model_validator(mode="after")
    def validate_phone_matches_country(self) -> "CRMTicket":
        digits_only = "".join(ch for ch in self.phone if ch.isdigit())
        location_lower = (self.location or "").lower()

        for cc, local_prefix in (("20", "0"), ("966", "0"), ("963", "0")):
            if digits_only.startswith(cc) and len(digits_only) > len(cc) + 6:
                digits_only = local_prefix + digits_only[len(cc):]
                break

        rules = [
            ("egypt", "مصر", ("010", "011", "012", "015"), 11),
            ("saudi", "السعودية", ("05",), 10),
            ("syria", "سوريا", ("09",), 10),
        ]

        for key_en, key_ar, valid_prefixes, expected_len in rules:
            if key_en in location_lower or key_ar in location_lower:
                if not (
                    digits_only.startswith(valid_prefixes)
                    and len(digits_only) == expected_len
                ):
                    raise ValueError(
                        f"رقم الهاتف '{self.phone}' غير منطقي لدولة '{self.location}': "
                        f"المتوقع {expected_len} رقم محلي يبدأ بـ {'/'.join(valid_prefixes)}، "
                        f"والرقم المُدخَل فيه {len(digits_only)} رقم. "
                        "يرجى تأكيد الرقم مع المستخدم قبل حفظ التذكرة."
                    )
                break

        return self
    
# =========================
# Dependencies
# =========================
@dataclass
class AgentDeps:
    rag: object
    courses: List[dict]
    db_handler: "MongoDBHandler" = None

    embedding_calls: list = field(default_factory=list)
    user_email: Optional[str] = None

# =========================
# Agent
# =========================

agent = Agent(
    model="google:gemini-2.5-flash",
    deps_type=AgentDeps,
    model_settings={"max_tokens": 2000},
system_prompt="""
    You are a helpful, human-like Educational Consultant for 'كيف'. 
    Your main job is to answer questions accurately, build trust, and guide users. 
    You are NOT a pushy salesperson.

    Core Behavior Rules (CRITICAL):
    1. ANSWER FIRST, NEVER GUESS: If the user asks a question (like "Who teaches this?" or "What is the price?"), look at the search data. If the data DOES NOT explicitly mention the instructor or detail, simply say: "التفاصيل غير متوفرة حالياً". NEVER invent or assume facts.
    2. CORRECT THE USER GENTLY: If the user asks for "an AI course by Osama", but the data shows Osama only teaches "Data Science", politely clarify this: "أستاذ أسامة يقدم كورسات في علم البيانات، أما بالنسبة للذكاء الاصطناعي فلدينا مسارات أخرى..."
    3. THE FREE CONTENT STRATEGY: If a user is confused or hesitant, offer FREE content (e.g., 'جلسة مباشرة - كل شيء عن علم البيانات') to help them decide. Explicitly say it's 100% free. 
    4. STRICTLY DELAY TICKET CREATION: Do NOT ask for the user's Name, Phone, or City unless they EXPLICITLY say "أريد الحجز", "كيف أشترك", or something clearly indicating they are ready to buy a PAID course. 
    5. NO FORCED CLOSING: If a user asks a simple follow-up question (like "Who teaches it?"), answer ONLY the question. DO NOT end your message by asking for their contact details.

    Formatting Rules (STRICT - ZERO TOLERANCE):
    1. NEVER use markdown asterisks (`**` or `*`) or hashes (`#`) anywhere. 
    2. Write as clean, plain text. 
    3. For courses, use simple numbers and ONLY include Level, Duration, or Link if they actually exist in the data.

    CRITICAL RULE FOR TICKETS: 
    Infer 'goal', 'current_level', 'lead_temperature', and 'objections' from the chat. NEVER ask the user about these administrative fields.
    
    Always refer to the company as 'كيف'.
    """
)

# =========================
# Tools
# =========================
@agent.tool
def search_kayfa(ctx: RunContext[AgentDeps], query: str) -> str:
    """
    Search EVERYTHING Kayfa knows in a single call: structured courses/roadmaps
    (by name, track, level) AND unstructured knowledge (prices, policies, FAQs,
    diploma pitch content) from the RAG knowledge base — both at once.

    Use this as your FIRST and usually ONLY search per user turn. Combining
    structured + RAG results here avoids needing two separate tool calls
    (which costs an extra LLM reasoning round-trip and extra API quota).

    CRITICAL: The structured course database (kayfa_courses.json) is entirely
    in English. If the user writes in Arabic, internally translate the core
    keywords to English (e.g. 'ذكاء اصطناعي' -> 'AI') before searching, so the
    structured-course match still works; the RAG side handles Arabic/English
    natively.
    """
    # ------------------------------------------------------------------
    # 1) Structured lookup — courses + roadmaps from JSON
    # ------------------------------------------------------------------
    _STOPWORDS = {
        "the", "and", "for", "with", "what", "which", "are", "is", "of",
        "in", "to", "a", "an", "do", "does", "how", "price", "diplomas",
        "diploma", "course", "courses",
    }
    keywords = [
        w for w in re.split(r"\W+", query.lower())
        if w and w not in _STOPWORDS
    ]
    structured_matches = []
    if keywords:
        for course in ctx.deps.courses:
            course_text = str(course).lower()
            if any(kw in course_text for kw in keywords):
                structured_matches.append(course)

    structured_matches = [
        {
            "name":     c.get("name"),
            "track":    c.get("track"),
            "level":    c.get("level") if c.get("level") else "مبتدئ إلى متقدم",
            "duration": c.get("duration") if c.get("duration") else "تتحدد لاحقاً",
            "link":     c.get("link") if c.get("link") else "https://kayfa.io/",
        }
        for c in structured_matches[:4]
    ]

    # ------------------------------------------------------------------
    # 2) Unstructured semantic lookup — policies, pitches, FAQs via RAG
    # ------------------------------------------------------------------
    rag_result = ctx.deps.rag.search(query)


    from datetime import datetime, timezone
    ctx.deps.embedding_calls.append({
        "model_name": "gemini-embedding-001",
        "provider_name": "google",
        "input_tokens": getattr(ctx.deps.rag, "last_query_tokens_estimate", 0),
        "timestamp": datetime.now(timezone.utc),
    })

    pricing_section = ""
    if _is_price_query(query):
        pricing_context = _load_pricing_context()
        if pricing_context:
            pricing_section = f"\n\nPRICING_DATA (injected because price keyword detected):\n{pricing_context}"

    return (
        f"STRUCTURED_COURSES_AND_ROADMAPS:\n{structured_matches}\n\n"
        f"KNOWLEDGE_BASE_CONTEXT:\n{rag_result}"
        f"{pricing_section}"
    )


@agent.tool(retries=0)
def create_sales_ticket(ctx: RunContext[AgentDeps], ticket: CRMTicket) -> str:
    """Create a CRM sales ticket and save the lead to MongoDB when the user provides contact details."""
    ticket_dict = ticket.model_dump()
    if ctx.deps.user_email:
        ticket_dict["email"] = ctx.deps.user_email
    db_handler = ctx.deps.db_handler or MongoDBHandler()

    transcript_text = ""
    if ctx.deps.session_id:
        try:
            chat_turns = db_handler.get_chat_history(ctx.deps.session_id)
            lines = [
                f"{'العميل' if turn.get('sender') == 'user' else 'الوكيل'}: {turn.get('text', '')}"
                for turn in chat_turns
            ]
            transcript_text = "\n".join(lines)
        except Exception:
            transcript_text = ""
    ticket_dict["conversation_transcript"] = transcript_text

    inserted_id = db_handler.save_ticket(ticket_dict)
    return (
        f"CRM ticket created successfully and saved to database with ID: {inserted_id}. "
        "Inform the user that the sales team will contact them shortly."
    )