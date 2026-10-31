from datasets import load_dataset

DATASET_ID = "rag-datasets/rag-mini-wikipedia"

corpus = load_dataset(
    DATASET_ID,
    name="text-corpus",
    split="passages",
)

questions = load_dataset(
    DATASET_ID,
    name="question-answer",
    split="test",
)

print("CORPUS")
print(corpus)
print("Columns:", corpus.column_names)
print("First row:", corpus[0])

for index, row in enumerate(corpus):
    print(row)

    if index > 3:
        break

print("\nEVALUATION QUESTIONS")
print(questions)
print("Columns:", questions.column_names)
print("First row:", questions[0])
