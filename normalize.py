import re
import unicodedata
from schema import ResultType

METHOD_MAP = {
    "ko/tko":                       ResultType.TKO,   # ufcstats uses "KO/TKO" for both
    "knockout":                     ResultType.KO,
    "tko":                          ResultType.TKO,
    "technical knockout":           ResultType.TKO,
    "tko - doctor's stoppage":      ResultType.TKO,
    "doctor stoppage":              ResultType.TKO,
    "submission":                   ResultType.SUBMISSION,
    "sub":                          ResultType.SUBMISSION,
    "decision - unanimous":         ResultType.UNANIMOUS_DECISION,
    "unanimous decision":           ResultType.UNANIMOUS_DECISION,
    "decision - split":             ResultType.SPLIT_DECISION,
    "split decision":               ResultType.SPLIT_DECISION,
    "decision - majority":          ResultType.MAJORITY_DECISION,
    "majority decision":            ResultType.MAJORITY_DECISION,
    "technical decision":           ResultType.TECHNICAL_DECISION,
    "could not continue":           ResultType.TKO,
    "draw":                         ResultType.DRAW,
    "majority draw":                ResultType.DRAW,
    "split draw":                   ResultType.DRAW,
    "no contest":                   ResultType.NO_CONTEST,
    "nc":                           ResultType.NO_CONTEST,
    "overturned":                   ResultType.NO_CONTEST,
    "dq":                           ResultType.DISQUALIFICATION,
    "disqualification":             ResultType.DISQUALIFICATION,
}

# Known fighter name aliases -> canonical ID
ALIASES: dict[str, str] = {
    "mike_bisping":            "michael_bisping",
    "jonathan_jones":          "jon_jones",
    "jose_aldo_junior":        "jose_aldo",
    "anthony_johnson":         "anthony_rumble_johnson",
    "tj_dillashaw":            "thomas_john_dillashaw",
    "cj_vergara":              "cody_durden",       # example placeholder
}


def normalize_result(method: str, detail: str = "") -> ResultType:
    combined = f"{method} {detail}".strip().lower()
    for key, val in METHOD_MAP.items():
        if key in combined:
            return val
    raise ValueError(f"Unrecognized result: '{combined}'")


def normalize_name(name: str) -> str:
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")
    name = re.sub(r"[^a-z ]", "", name.lower()).strip()
    return " ".join(name.split())


def make_fighter_id(name: str) -> str:
    return normalize_name(name).replace(" ", "_")


def resolve_id(name: str) -> str:
    raw = make_fighter_id(name)
    return ALIASES.get(raw, raw)
