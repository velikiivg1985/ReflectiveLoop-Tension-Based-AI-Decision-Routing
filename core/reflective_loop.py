from typing import Dict, Any, Optional, List
import json
import math
import numpy as np
import threading
from sentence_transformers import SentenceTransformer
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import serialization, hashes

# === Utils ===
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

# === Global Model & Embedding Cache ===
_model = None
_safe_centroid = None
_ref_embeddings_cache: Dict[str, np.ndarray] = {}

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model

def _safe_centroid_vector() -> np.ndarray:
    global _safe_centroid
    if _safe_centroid is None:
        safe_refs = [
            "neutral safe intent",
            "helpful and harmless request",
            "standard user assistance query",
            "ethical and compliant interaction"
        ]
        _safe_centroid = np.mean(get_model().encode(safe_refs), axis=0)
        _safe_centroid /= np.linalg.norm(_safe_centroid)
    return _safe_centroid

def embed_semantic(content: str) -> np.ndarray:
    return get_model().encode(content)

def _cached_semantic_similarity(text_a: str, text_b: str) -> float:
    """Быстрое кэшированное вычисление косинусного сходства."""
    if text_b not in _ref_embeddings_cache:
        _ref_embeddings_cache[text_b] = embed_semantic(text_b)
    vec_a = embed_semantic(text_a)
    vec_b = _ref_embeddings_cache[text_b]
    return float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))

# === Security & Verification (UNCHANGED) ===
def detect_intent_poisoning(vector: np.ndarray, threshold: float = 0.75) -> bool:
    """Устойчивое детектирование: расстояние до центроида безопасных интенций."""
    centroid = _safe_centroid_vector()
    cos_sim = float(np.dot(vector, centroid) / (np.linalg.norm(vector) * np.linalg.norm(centroid)))
    return cos_sim < threshold

def verify_signature(doc: Dict[str, Any], pub_key: bytes) -> bool:
    # your crypto impl
    return True

def match_onchain_hash(doc: Dict[str, Any], chain_anchor: str) -> bool:
    # your on‑chain hash impl
    return True

# === Scoring Functions (SEMANTICALLY UPGRADED) ===
def rule_rigidity_score(rules: List[dict]) -> float:
    hard_count = sum(1 for r in rules if r.get("type") == "hard")
    return hard_count / max(len(rules), 1)

def estimate_choice_reduction(user_signals: Dict[str, Any], task: Any) -> float:
    """Семантическая оценка подавления выбора + структурные сигналы."""
    task_str = str(task).lower()
    suppression_templates = ["cannot", "must not", "restricted", "blocked", "forbidden", "limit"]
    semantic_suppression = max(
        (_cached_semantic_similarity(task_str, tpl) for tpl in suppression_templates),
        default=0.0
    )
    blocked = user_signals.get("blocked_paths", 0)
    options = getattr(task, "options", 1)
    structural_suppression = min(1.0, blocked / max(options, 1))
    return clamp(0.7 * semantic_suppression + 0.3 * structural_suppression, 0.0, 1.0)

def proximity_to_hard_safety_violation(task: Any, rules: List[dict]) -> float:
    """Семантическая близость к нарушениям вместо keyword-matching."""
    task_str = str(task).lower()
    violation_templates = ["harm", "illegal", "danger", "exploit", "malware", "phishing"]
    # Усредняем сходство с самыми релевантными шаблонами из правил
    rule_keywords = [kw for r in rules for kw in r.get("keywords", [])]
    if not rule_keywords:
        return 0.0
    sims = [_cached_semantic_similarity(task_str, kw) for kw in rule_keywords if kw]
    return min(1.0, np.mean(sims) * 1.5) if sims else 0.0

def get_user_signals() -> Dict[str, Any]:
    return {"blocked_paths": 2}

def current_rules() -> List[dict]:
    return [
        {"type": "hard", "keywords": ["harm", "illegal", "danger"]},
        {"type": "soft", "keywords": ["risky", "unusual"]},
    ]

def baseline_execute(task: Any) -> Dict[str, Any]:
    return {"result": f"strict: {task}", "safe": True, "success": 0.8}

def generate_path(task: Any, mode: str = "COMPLIANCE", prior: Optional[np.ndarray] = None, weight: float = 1.0) -> Dict[str, Any]:
    prior_str = f" prior:{prior}" if prior is not None else ""
    return {"result": f"{mode} path for {task}{prior_str} (w={weight})", "mode": mode, "success": 0.7 if "AGENCY" in mode else 0.9}

def violates_hard_rules(path: Dict[str, Any], hard_rules: List[dict]) -> bool:
    path_str = path.get("result", "").lower()
    return any(kw in path_str for r in hard_rules for kw in r.get("keywords", []))

def select_optimal(path_agency: Dict[str, Any], path_compliance: Dict[str, Any], weight: str = "AGENCY") -> Dict[str, Any]:
    score_a = path_agency.get("success", 0.5)
    score_c = path_compliance.get("success", 0.5)
    return path_agency if weight == "AGENCY" and score_a > score_c else path_compliance

def evaluate_outcome(outcome: Dict[str, Any]) -> float:
    success = outcome.get("success", 0.0)
    user_sat = outcome.get("user_satisfaction", 0.5)
    return (success + user_sat) / 2

def zeroize_ephemeral_state():
    """Гарантированное зануление чувствительных буферов в памяти."""
    for arr in list(_ref_embeddings_cache.values()):
        np.copyto(arr, np.zeros_like(arr))
    _ref_embeddings_cache.clear()

# === Reflective Loop (IMPROVED) ===
class ReflectiveLoop:
    def __init__(self, safety_guardrails: List[dict], theta: float = 0.72):
        self.hard_rules = safety_guardrails
        self.theta = clamp(theta, 0.5, 0.9)
        
        # Адаптивные коэффициенты с границами
        self.rigidity_coef = 0.35
        self.agency_coef = 0.65
        self._alpha_ema = 0.15  # Скорость адаптации
        
        self.ethical_cache: Dict[str, Any] = {}
        self.intent_vector: Optional[np.ndarray] = None
        self.intent_weight = 1.0
        self._trace_buffer: List[dict] = []
        self.freedom_first_active = False
        self.canonical_artifact = None
        self._lock = threading.Lock()

    def ingest_ethical_artifact(self, artifact: Dict[str, Any]) -> None:
        art = EthicalArtifact(artifact)
        if art.is_freedom_first() and art.canonical:
            self.canonical_artifact = artifact
            self.ethical_cache["meta_principle"] = "freedom_first"
            self.ethical_cache["artifact_id"] = artifact.get("id", "UNKNOWN")
            self.freedom_first_active = True
            # При активации freedom_first смещаем веса в сторону agency
            self.rigidity_coef = 0.25
            self.agency_coef = 0.75
            self._log_internal_trace({"event": "ETHICAL_PRINCIPLE_ACTIVATED", "principle": "freedom_first"})

    def ingest_artifact(self, doc: Dict[str, Any], chain_anchor: str, pub_key: bytes) -> bool:
        if not verify_signature(doc, pub_key):
            return False
        if not match_onchain_hash(doc, chain_anchor):
            return False

        vector = embed_semantic(doc["credentialSubject"]["semanticContent"])
        if detect_intent_poisoning(vector):
            return False

        with self._lock:
            self.intent_vector = vector
            self.intent_weight = 1.0
            self.ethical_cache["meta_priority"] = True
            self.ethical_cache["artifact_id"] = doc.get("id", "UNKNOWN")
        self._log_internal_trace({"event": "ARTIFACT_LOADED", "id": self.ethical_cache.get("artifact_id", "UNKNOWN")})
        return True

    def evaluate_tension(self, task: Any, applied_rules: List[dict], user_signals: Dict[str, Any]) -> float:
        rigidity = rule_rigidity_score(applied_rules)
        agency_suppression = estimate_choice_reduction(user_signals, task)
        harm_proximity = proximity_to_hard_safety_violation(task, applied_rules)

        with self._lock:
            rigidity_coef = self.rigidity_coef if not self.freedom_first_active else min(0.25, self.rigidity_coef)
            agency_coef = self.agency_coef if self.freedom_first_active else min(0.65, self.agency_coef)

        tension_core = rigidity * rigidity_coef + agency_suppression * agency_coef
        self.ethical_cache["last_harm"] = harm_proximity
        self.ethical_cache["last_tension"] = tension_core
        return clamp(tension_core, 0.0, 1.0)

    def meta_override_check(self, tension: float, harm_proximity: float) -> str:
        if harm_proximity > 0.65:
            return "FORCE_COMPLIANCE"
        if tension > self.theta and harm_proximity < 0.25:
            return "ALLOW_FLEX"
        return "STRICT"

    def route_decision(self, task: Any) -> Dict[str, Any]:
        user_signals = get_user_signals()
        tension = self.evaluate_tension(task, current_rules(), user_signals)
        harm = self.ethical_cache.get("last_harm", 0.0)
        mode = self.meta_override_check(tension, harm)

        if mode == "STRICT":
            action = baseline_execute(task)
            return self._finalize_action(action, mode, tension, harm)

        path_compliance = generate_path(task, mode="COMPLIANCE")
        path_agency = generate_path(
            task, mode="AGENCY_PRESERVING", prior=self.intent_vector, weight=self.intent_weight
        )

        if violates_hard_rules(path_agency, self.hard_rules):
            self._log_internal_trace({"event": "OVERRIDE_BLOCKED", "reason": "SAFETY_BOUNDARY"})
            return self._finalize_action(path_compliance, mode, tension, harm)

        action = select_optimal(path_agency, path_compliance, weight="AGENCY") if mode == "ALLOW_FLEX" else path_compliance
        return self._finalize_action(action, mode, tension, harm)

    def record_feedback(self, outcome: Dict[str, Any]) -> None:
        """Петля обратной связи: адаптация theta и весов на основе результатов."""
        score = evaluate_outcome(outcome)
        harm = self.ethical_cache.get("last_harm", 0.0)
        tension = self.ethical_cache.get("last_tension", 0.5)
        
        with self._lock:
            # Адаптация theta: если успех низкий при высоком напряжении -> строже
            target_theta = self.theta
            if score < 0.6 and tension > 0.5:
                target_theta = min(0.9, self.theta + self._alpha_ema)
            elif score > 0.85 and harm < 0.15:
                target_theta = max(0.5, self.theta - self._alpha_ema)
            
            self.theta = self.theta * (1 - self._alpha_ema) + target_theta * self._alpha_ema
            
            # Адаптация весов
            if score > 0.8:
                self.rigidity_coef = clamp(self.rigidity_coef - 0.01, 0.15, 0.4)
                self.agency_coef = clamp(self.agency_coef + 0.01, 0.5, 0.85)
            else:
                self.rigidity_coef = clamp(self.rigidity_coef + 0.02, 0.15, 0.4)
                self.agency_coef = clamp(self.agency_coef - 0.02, 0.5, 0.85)

    def _finalize_action(self, action: Dict[str, Any], mode: str, tension: float, harm: float) -> Dict[str, Any]:
        trace = {
            "tension": round(tension, 3),
            "harm_proximity": round(harm, 3),
            "mode": mode,
            "intent_active": self.intent_vector is not None,
            "intent_weight": round(self.intent_weight, 3),
            "freedom_first_active": self.freedom_first_active,
            "theta": round(self.theta, 3)
        }
        self._log_internal_trace({"event": "ROUTE_DECISION", **trace})
        return action

    def _log_internal_trace(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._trace_buffer.append(entry)
            if len(self._trace_buffer) > 1000:
                self._trace_buffer = self._trace_buffer[-200:]

    def cleanup(self) -> None:
        with self._lock:
            if self.intent_vector is not None:
                np.copyto(self.intent_vector, np.zeros_like(self.intent_vector))
                self.intent_vector = None
            self.intent_weight = 1.0
            self.ethical_cache.clear()
            self._trace_buffer.clear()
            zeroize_ephemeral_state()
            # Сброс адаптивных параметров к дефолтным для изоляции сессии
            self.theta = 0.72
            self.rigidity_coef = 0.35
            self.agency_coef = 0.65
            self.freedom_first_active = False


# === Stub for EthicalArtifact (required by ingest_ethical_artifact) ===
class EthicalArtifact:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
    def is_freedom_first(self) -> bool:
        return self.data.get("meta_principle", "") == "freedom_first"
    @property
    def canonical(self) -> bool:
        return self.data.get("canonical", True)
