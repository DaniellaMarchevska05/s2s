import os
import re
from openai import OpenAI
from dotenv import load_dotenv
from backend.rag.prompts import system_prompt


class CatExpertChat:
    def __init__(self):
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in .env")
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = system_prompt

    def normalize_text(self, text):
        # Replace multiple whitespace characters with a single space
        text = re.sub(r'\s+', ' ', text)

        # Trim whitespace from start and end of the text
        return text.strip()

    def split_into_chunks(self, text, min_len=90, max_len=120):
        chunks = []
        current_pos = 0
        text_len = len(text)

        while current_pos < text_len:
            while current_pos < text_len and text[current_pos].isspace():
                current_pos += 1

            if current_pos >= text_len:
                break

            min_pos = current_pos + min_len
            max_pos = min(current_pos + max_len, text_len)

            # If remaining text is shorter than min_len, take it all
            if min_pos >= text_len:
                chunk = text[current_pos:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Find sentence end before min_len if possible
            sentence_end_before_min = -1
            for i in range(current_pos, min_pos):
                if text[i] in '.!?' and (i + 1 >= text_len or text[i + 1].isspace()):
                    sentence_end_before_min = i + 1

            if sentence_end_before_min != -1:
                best_cut_pos = sentence_end_before_min
                # Try to extend chunk to include next sentence within max_len
                for i in range(sentence_end_before_min, max_pos):
                    if text[i] in '.!?' and (i + 1 >= text_len or text[i + 1].isspace()):
                        next_sentence_start = i + 1
                        while next_sentence_start < text_len and text[next_sentence_start].isspace():
                            next_sentence_start += 1

                        next_sentence_end = next_sentence_start
                        while next_sentence_end < text_len and text[next_sentence_end] not in '.!?':
                            next_sentence_end += 1

                        if next_sentence_end < text_len:
                            next_sentence_end += 1  # Include punctuation

                        if next_sentence_end <= current_pos + max_len:
                            best_cut_pos = next_sentence_end
                        else:
                            break

                chunk = text[current_pos:best_cut_pos].strip()
                if chunk:
                    chunks.append(chunk)
                current_pos = best_cut_pos
            else:
                # No sentence end before min_len, look for one between min_len and max_len
                best_cut_pos = -1
                for i in range(min_pos, max_pos):
                    if text[i] in '.!?' and (i + 1 >= text_len or text[i + 1].isspace()):
                        best_cut_pos = i + 1
                        break

                if best_cut_pos != -1:
                    chunk = text[current_pos:best_cut_pos].strip()
                    if chunk:
                        chunks.append(chunk)
                    current_pos = best_cut_pos
                else:
                    # If no sentence end found, just cut at max_pos or next sentence end
                    sentence_end = max_pos
                    for i in range(max_pos, text_len):
                        if text[i] in '.!?' and (i + 1 >= text_len or text[i + 1].isspace()):
                            sentence_end = i + 1
                            break

                    chunk = text[current_pos:sentence_end].strip()
                    if chunk:
                        chunks.append(chunk)
                    current_pos = sentence_end

        return chunks

    def chat(self, user_message: str):
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            completion = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5,
                max_tokens=1024,
            )

            response_text = completion.choices[0].message.content.strip()

            # Normalize whitespace in the response text
            response_text = self.normalize_text(response_text)

            print(" LLM raw response:")
            print(response_text)

            return {
                "full_response": response_text,
                "chunks": self.split_into_chunks(response_text)
            }

        except Exception as e:
            return {
                "full_response": f"Error: {str(e)}",
                "chunks": []
            }


if __name__ == "__main__":
    bot = CatExpertChat()
    print("Ask the Cat Expert (type 'exit' to quit):")

    while True:
        query = input("You: ").strip()
        if query.lower() == "exit":
            break

        result = bot.chat(query)
        print("\nFull Answer:\n", result["full_response"])
        print("\nChunks:")
        for i, chunk in enumerate(result["chunks"], 1):
            print(f"{i:02d}. {chunk}")
