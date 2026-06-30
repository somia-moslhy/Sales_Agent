# Kayfa AI Sales Agent

**AI-Powered Sales Assistant | AI and Analytics Internship Project**

An intelligent AI sales agent developed for **Kayfa**, designed to engage with users, recommend personalized learning paths, and convert conversations into actionable sales leads.

The agent supports multiple Arabic dialects and English, leverages Retrieval-Augmented Generation (RAG) for accurate responses, and integrates with a CRM system powered by MongoDB.

---

## Features

* **Multilingual Support**
  Communicates in English and Arabic dialects (Egyptian, Saudi, Syrian, and Modern Standard Arabic).

* **Context-Aware Responses**
  Uses RAG to ensure responses are grounded in the internal knowledge base.

* **Smart Recommendations**
  Suggests relevant Kayfa courses and learning roadmaps based on user needs.

* **CRM Integration**
  Extracts user details (Name, Phone, City) and generates structured lead tickets.

* **Cost Optimization**
  Implements lightweight routing for casual conversations to reduce API usage.

---

## Tech Stack

| Layer            | Technology                                       |
| ---------------- | ------------------------------------------------ |
| **Frontend**     | Streamlit (RTL Support)                          |
| **AI Agent**     | Pydantic-AI + Google Gemini (`gemini-2.5-flash`) |
| **RAG Pipeline** | LangChain + ChromaDB + Gemini Embeddings         |
| **Database**     | MongoDB Atlas                                    |
| **Utilities**    | python-dotenv, certifi, dnspython                |

---

## Project Structure

```text
AI_Sales_Agent/
├── app.py                  # Main chat interface
├── pages/
│   └── crm.py             # CRM dashboard
├── core/                  # Agent logic and RAG pipeline
├── data/                  # Knowledge base (Markdown and JSON)
├── database/              # MongoDB handlers
├── build_vector_db.py     # Vector DB initialization
└── requirements.txt       # Dependencies
```

---

## Setup and Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file and add:

```env
GOOGLE_API_KEY=your_api_key
MONGODB_URI=your_mongodb_uri
APP_PASSWORD=your_password
```

---

### 3. Build the Knowledge Base

```bash
python build_vector_db.py
```

---

### 4. Run the Application

```bash
streamlit run app.py
```

---

## How It Works

1. The user sends a message through the chat interface
2. The agent detects the language automatically
3. The query is processed using RAG
4. Relevant content is retrieved from the knowledge base
5. A response is generated using Gemini
6. If the user shows buying intent, a CRM ticket is created

---

## Security and Deployment

* Do not upload the `.env` file to GitHub
* Use secrets management in deployment platforms
* Configure MongoDB Atlas network access
* Ensure the vector database is built before deployment

---

## Contribution

This project was developed as part of the **Kayfa AI Engineering Internship**.

To maintain system accuracy:

* Keep the `data/` structure consistent
* Ensure all new content is properly indexed

---

## Future Improvements

* Add WhatsApp integration
* Enhance lead scoring using machine learning
* Deploy using Docker and CI/CD pipelines
* Add analytics dashboard for sales insights

---

Powered by Pydantic-AI and Google Gemini.
