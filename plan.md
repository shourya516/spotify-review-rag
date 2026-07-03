Problem

How might we enable Product Managers to ask natural-language questions about Spotify user feedback and receive accurate, evidence-backed insights generated from real user reviews collected across multiple platforms?

The solution should automatically collect, clean, and organize reviews from the Google Play Store, Apple App Store, and Reddit, and use Retrieval-Augmented Generation (RAG) to retrieve the most relevant reviews before generating answers. Responses should be grounded in actual user feedback, minimizing hallucinations while providing citations to supporting reviews.

Objectives

Build a deployable, full-stack AI application that:

Automatically scrapes Spotify reviews from Google Play Store, Apple App Store, and Reddit.
Cleans and preprocesses the collected reviews by removing duplicates, spam, HTML, URLs, and other noise.
Stores the processed reviews in a PostgreSQL database.
Generates vector embeddings for semantic search.
Implements a Retrieval-Augmented Generation (RAG) pipeline to answer product-related questions using retrieved reviews as context.
Provides a web-based interface where users can:
Trigger review scraping.
Monitor data ingestion status.
Ask product-related questions in natural language.
View AI-generated answers along with the supporting reviews used as evidence.
Target Users
Product Managers
Growth Teams
User Research Teams
Customer Experience Teams
Product Analysts
Example Questions

The system should answer questions such as:

Why do users struggle to discover new music?
What are the most common complaints about Spotify recommendations?
Which features are requested most frequently?
What issues are most commonly reported after recent updates?
What differences exist between Play Store reviews and Reddit discussions?
How do premium users' concerns differ from free users' concerns?
What product opportunities emerge from recent user feedback?
Success Criteria

The application will be considered successful if it can:

Automatically ingest reviews from multiple public sources.
Maintain an up-to-date review repository.
Retrieve the most relevant reviews for a given query using semantic search.
Generate concise, evidence-backed responses with citations.
Be deployed as a full-stack web application with separate frontend and backend services.
Scope
In Scope
Review scraping from Google Play Store, Apple App Store, and Reddit.
Data cleaning and preprocessing.
PostgreSQL database.
Vector embeddings.
Retrieval-Augmented Generation (RAG).
FastAPI backend.
Next.js frontend.
Deployable architecture.
Out of Scope
Fine-tuning large language models.
Real-time streaming review ingestion.
User authentication and authorization.
Predictive analytics and recommendation model improvements.
Multi-product support (initially limited to Spotify)