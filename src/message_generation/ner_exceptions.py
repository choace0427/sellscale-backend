""" Exceptions for entities in the NER

These exceptions will be stripped from the NER before being compared against the prompt.

For example:
    prompt: "Aakash Adesara, MD"
    completion: "Dr. Adesara"
    NER: ["Dr. Adesara"]

    We strip the 'Dr.' away before comparing the NER to the prompt.
"""
ner_exceptions = [" Dr. ", " Dr "]

title_abbreviations = {
    "ceo": "chief executive officer",
    "cfo": "chief financial officer",
    "cto": "chief technology officer",
    "cmo": "chief marketing officer",
    "coo": "chief operating officer",
    "cio": "chief information officer",
    "cto": "chief technical officer",
    "cdo": "chief data officer",
    "cpo": "chief product officer",
    "cro": "chief revenue officer",
    "cso": "chief security officer",
    "clo": "chief legal officer",
    "cao": "chief analytics officer",
    "cco": "chief compliance officer",
    "chro": "chief human resources officer",
    "ciso": "chief information security officer",
    "cqo": "chief quality officer",
    "cvo": "chief visionary officer",
    "cbo": "chief business officer",
    "cco": "chief creative officer",
    "cio": "chief investment officer",
    "cmo": "chief medical officer",
}
