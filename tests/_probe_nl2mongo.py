"""Probe nl2mongo output format with sample questions."""
import sys, json
sys.path.insert(0, ".")

from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

print("Loading model Chirayu/nl2mongo ...")
tokenizer = AutoTokenizer.from_pretrained("Chirayu/nl2mongo")
model = AutoModelForSeq2SeqLM.from_pretrained("Chirayu/nl2mongo")
device = "cuda" if torch.cuda.is_available() else "cpu"
model = model.to(device)
print(f"  Loaded on {device}\n")

fields = "title, plot, genres, cast, directors, year, runtime, rated, type, released, imdb.rating, imdb.votes, awards.wins, awards.nominations, num_mflix_comments"

questions = [
    "which movies are of genre Action?",
    "find movies directed by Christopher Nolan",
    "which movies have imdb rating greater than 8?",
    "count movies grouped by genre",
    "find top 5 movies with highest imdb rating",
]

for q in questions:
    prompt = f"mongo: {q} | movies : {fields}"
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = model.generate(
            **inputs,
            num_beams=10,
            max_length=256,
            repetition_penalty=2.5,
            length_penalty=1.0,
            early_stopping=True,
        )
    raw = tokenizer.decode(out[0], skip_special_tokens=True)
    print(f"Q: {q}")
    print(f"A: {raw}")
    print()
