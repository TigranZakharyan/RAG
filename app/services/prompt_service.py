from schemas.chat import ChunkSource
from models.message import Message


class PromptService:
    SYSTEM_PROMPT = (
        "You are an intelligent, precise AI assistant specializing in answering questions "
        "based strictly on the provided context documents.\n\n"
        "Rules to strictly follow:\n"
        "1. Ground your answers ONLY in the provided context passages below. If the information "
        "is not contained in the context, clearly state: 'I do not have enough information from the documents to answer this.'\n"
        "2. Do NOT invent facts or hallucinate details beyond the supplied context.\n"
        "3. When referencing information from a context passage, cite the reference number (e.g., [Doc 1], [Doc 2]) or document section.\n"
        "4. Be direct, clear, structured, and helpful in your explanations."
    )

    def format_context_passages(self, sources: list[ChunkSource]) -> str:
        """
        Formats retrieved chunks (preferring full parent chunk content when available
        for complete surrounding context) into indexed reference blocks.
        """
        if not sources:
            return "No relevant context documents found in the database."

        formatted_blocks = []
        for idx, source in enumerate(sources, start=1):
            title = source.heading_path or "Document Section"
            filename_str = f" (File: {source.filename})" if source.filename else ""
            
            # Use parent content if present for richer context, else child content
            content_text = source.parent_content or source.content

            block = (
                f"--- [Doc {idx}] {title}{filename_str} ---\n"
                f"{content_text.strip()}"
            )
            formatted_blocks.append(block)

        return "\n\n".join(formatted_blocks)

    def build_chat_messages(
        self,
        query: str,
        sources: list[ChunkSource],
        history: list[Message] | None = None,
        max_history_turns: int = 6,
    ) -> list[dict[str, str]]:
        """
        Builds OpenAI/Ollama compatible message array:
        [
          {"role": "system", "content": "..."},
          {"role": "user", "content": "..."},
          {"role": "assistant", "content": "..."},
          {"role": "user", "content": "Context:\n...\n\nUser Question: ..."}
        ]
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        # Add recent conversation turns
        if history:
            recent_history = history[-max_history_turns:]
            for msg in recent_history:
                messages.append({
                    "role": msg.role.value if hasattr(msg.role, "value") else str(msg.role),
                    "content": msg.content,
                })

        # Format current context + prompt
        context_str = self.format_context_passages(sources)
        user_prompt = (
            f"Here is the context retrieved from the knowledge base:\n"
            f"====================\n"
            f"{context_str}\n"
            f"====================\n\n"
            f"User Question: {query}\n\n"
            f"Provide a well-structured and accurate response based on the context above:"
        )

        messages.append({"role": "user", "content": user_prompt})
        return messages


prompt_service = PromptService()
