"""
LLM Service — talks to Groq's API for fast inference.

Builds prompts from retrieved context and conversation history,
calls the LLM with retry logic, and handles failures gracefully.
"""

import logging
from typing import List, Optional, Tuple

import tiktoken
from groq import Groq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.config import settings
from app.models.chunk import Chunk
from app.models.message import Message

logger = logging.getLogger(__name__)

# groq client — uses the api key from settings
client = Groq(api_key=settings.GROQ_API_KEY)

# system prompt that keeps the model grounded
SYSTEM_PROMPT = """You are a precise and helpful document Q&A assistant. Your role is to answer questions based ONLY on the provided document context.

STRICT RULES:
1. Answer ONLY based on the provided context from the document.
2. If the answer cannot be found in the provided context, respond with: "Answer not found in the provided document context."
3. Be concise, factual, and direct in your responses.
4. When possible, reference which part of the context supports your answer.
5. Do NOT make up information or use external knowledge.
6. Do NOT hallucinate facts that are not in the context.
7. If the question is ambiguous, ask for clarification.
8. Format your response clearly with proper structure when listing multiple points."""


def _count_tokens(text: str, model: str = "gpt-3.5-turbo") -> int:
    """Count tokens using tiktoken (works as a rough estimate for llama models too)."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def _truncate_context(
    chunks: List[Tuple[Chunk, float]],
    max_tokens: int = 3000,
) -> str:
    """
    Build context string from chunks, respecting token budget.
    Higher-scored chunks get priority. Stops when we'd exceed the limit.
    """
    context_parts: List[str] = []
    total_tokens = 0

    for i, (chunk, score) in enumerate(chunks):
        chunk_text = f"[Source {i + 1} | Relevance: {score:.2f}]\n{chunk.content}"
        chunk_tokens = _count_tokens(chunk_text)

        if total_tokens + chunk_tokens > max_tokens:
            remaining = max_tokens - total_tokens
            if remaining > 100:
                ratio = remaining / chunk_tokens
                truncated = chunk_text[: int(len(chunk_text) * ratio)]
                context_parts.append(truncated + "...")
            break

        context_parts.append(chunk_text)
        total_tokens += chunk_tokens

    return "\n\n---\n\n".join(context_parts)


def _build_conversation_history(
    previous_messages: List[Message],
    max_turns: int = 3,
) -> List[dict]:
    """
    Grab the last N turns of conversation so the model has context
    for follow-up questions.
    """
    recent = previous_messages[-(max_turns * 2):]
    history = []
    for msg in recent:
        role = msg.role.value if hasattr(msg.role, 'value') else msg.role
        history.append({"role": role, "content": msg.content})
    return history


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    before_sleep=lambda retry_state: logger.warning(
        f"Groq API call failed, retrying (attempt {retry_state.attempt_number})..."
    ),
)
def _call_groq(messages: List[dict], model: str, max_tokens: int) -> str:
    """
    Hit the Groq API with retries. Groq is fast but can still
    have transient failures, so we retry up to 3 times.
    """
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.1,  # low temp for factual answers
        top_p=1,
    )
    return response.choices[0].message.content or ""


class LLMService:
    """Service layer for generating answers via Groq."""

    @staticmethod
    def generate_answer(
        question: str,
        relevant_chunks: List[Tuple[Chunk, float]],
        previous_messages: Optional[List[Message]] = None,
    ) -> str:
        """
        Takes a question + relevant chunks + optional conversation history,
        builds a prompt, and gets an answer from the LLM.
        """
        if not relevant_chunks:
            return "No relevant context found in the document to answer your question."

        # build context with token budget
        context = _truncate_context(relevant_chunks, max_tokens=3000)

        # assemble the messages array
        messages: List[dict] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]

        # tack on conversation history if we have it
        if previous_messages:
            history = _build_conversation_history(previous_messages, max_turns=3)
            messages.extend(history)

        # the actual question with context
        user_message = f"""Based on the following document context, answer the question.

DOCUMENT CONTEXT:
{context}

QUESTION: {question}

Remember: Answer ONLY from the provided context. If the answer is not in the context, say "Answer not found in the provided document context."
"""
        messages.append({"role": "user", "content": user_message})

        # quick token check
        total_prompt_tokens = sum(_count_tokens(m["content"]) for m in messages)
        logger.info(f"Total prompt tokens (approx): {total_prompt_tokens}")

        if total_prompt_tokens > 6000:
            logger.warning(f"High token count ({total_prompt_tokens}), might want to trim context")

        # call groq
        try:
            answer = _call_groq(
                messages=messages,
                model=settings.LLM_MODEL,
                max_tokens=settings.LLM_MAX_TOKENS,
            )
            logger.info(f"Got answer from Groq ({_count_tokens(answer)} tokens)")
            return answer

        except Exception as e:
            logger.error(f"Groq API failed after retries: {e}")
            return (
                "I apologize, but I'm currently unable to process your question due to a "
                "temporary service issue. Please try again in a few moments. "
                "If the issue persists, the relevant document excerpts are available "
                "in the source chunks for manual review."
            )
