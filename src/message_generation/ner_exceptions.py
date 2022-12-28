""" Exceptions for entities in the NER

These exceptions will be stripped from the NER before being compared against the prompt.

For example:
    prompt: "Aakash Adesara, MD"
    completion: "Dr. Adesara"
    NER: ["Dr. Adesara"]

    We strip the 'Dr.' away before comparing the NER to the prompt.
"""
ner_exceptions = [
    "Dr.",
]
