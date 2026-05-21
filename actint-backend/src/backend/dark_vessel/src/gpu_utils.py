"""
GPU / Compute Utility

Provides a unified model factory that selects the best available backend:
  1. XGBoost  GPU (CUDA) — fastest for tabular data on RTX 4080
  2. LightGBM GPU (CUDA) — alternative
  3. XGBoost  CPU (n_jobs = all cores)
  4. sklearn RandomForest  — fallback

Usage:
    from src.gpu_utils import make_classifier, compute_device, BACKEND
"""

import os
import multiprocessing
import numpy as np

N_CORES = multiprocessing.cpu_count()

# ── Detect best available backend ────────────────────────────────────────────

def _detect_backend() -> str:
    try:
        import xgboost as xgb, numpy as np
        dm = xgb.DMatrix(np.ones((4, 2)), label=[0, 1, 0, 1])
        xgb.train({"device": "cuda", "tree_method": "hist",
                   "objective": "binary:logistic"}, dm,
                  num_boost_round=1, verbose_eval=False)
        return "xgboost_gpu"
    except Exception:
        pass

    try:
        import xgboost  # noqa
        return "xgboost_cpu"
    except ImportError:
        pass

    try:
        import lightgbm as lgb
        lgb.Dataset(np.ones((4, 2)), label=[0, 1, 0, 1])
        return "lightgbm_cpu"
    except ImportError:
        pass

    return "sklearn"


BACKEND = _detect_backend()
compute_device = "GPU (CUDA)" if "gpu" in BACKEND else f"CPU ({N_CORES} cores)"
# Only print in the main process — suppress in joblib worker forks
import multiprocessing as _mp
if _mp.current_process().name == "MainProcess":
    print(f"[gpu_utils] Backend: {BACKEND}  |  Device: {compute_device}")


# ── Model factories ───────────────────────────────────────────────────────────

class XGBWrapper:
    """sklearn-compatible wrapper around XGBoost Booster."""

    def __init__(self, n_classes: int = 2, n_estimators: int = 400,
                 max_depth: int = 8, learning_rate: float = 0.05,
                 use_gpu: bool = True, random_state: int = 42):
        self.n_classes     = n_classes
        self.n_estimators  = n_estimators
        self.max_depth     = max_depth
        self.learning_rate = learning_rate
        self.use_gpu       = use_gpu
        self.random_state  = random_state
        self._booster      = None
        self.classes_      = None
        self._label_offset = 0

    def _params(self) -> dict:
        p = {
            "max_depth":        self.max_depth,
            "learning_rate":    self.learning_rate,
            "subsample":        0.8,
            "colsample_bytree": 0.8,
            "min_child_weight": 3,
            "reg_lambda":       1.0,
            "seed":             self.random_state,
            "verbosity":        0,
        }
        if self.n_classes > 2:
            p["objective"]  = "multi:softprob"
            p["num_class"]  = self.n_classes
            p["eval_metric"]= "mlogloss"
        else:
            p["objective"]  = "binary:logistic"
            p["eval_metric"]= "logloss"

        if self.use_gpu and "gpu" in BACKEND:
            p["device"]      = "cuda"
            p["tree_method"] = "hist"
        else:
            p["device"]      = "cpu"
            p["tree_method"] = "hist"
            p["nthread"]     = N_CORES
        return p

    def fit(self, X: np.ndarray, y: np.ndarray):
        import xgboost as xgb
        self.classes_     = np.unique(y)
        self.n_classes    = len(self.classes_)
        # Re-map labels to 0..N-1
        label_map = {c: i for i, c in enumerate(self.classes_)}
        y_mapped  = np.array([label_map[yi] for yi in y])
        dm = xgb.DMatrix(X, label=y_mapped, missing=np.nan)
        self._booster = xgb.train(
            self._params(), dm,
            num_boost_round=self.n_estimators,
            verbose_eval=False,
        )
        self._label_map    = label_map
        self._inv_label_map = {v: k for k, v in label_map.items()}
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        import xgboost as xgb
        dm    = xgb.DMatrix(X, missing=np.nan)
        proba = self._booster.predict(dm)
        if self.n_classes == 2:
            idx = (proba > 0.5).astype(int)
        else:
            idx = proba.reshape(-1, self.n_classes).argmax(axis=1)
        return np.array([self._inv_label_map[i] for i in idx])

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        import xgboost as xgb
        dm    = xgb.DMatrix(X, missing=np.nan)
        proba = self._booster.predict(dm)
        if self.n_classes == 2:
            p1 = proba.reshape(-1, 1)
            return np.hstack([1 - p1, p1])
        return proba.reshape(-1, self.n_classes)

    @property
    def feature_importances_(self) -> np.ndarray:
        if self._booster is None:
            return np.array([])
        scores = self._booster.get_score(importance_type="gain")
        # Return in feature-index order (f0, f1, ...)
        n = self._booster.num_features()
        return np.array([scores.get(f"f{i}", 0.0) for i in range(n)])


class LGBMWrapper:
    """sklearn-compatible wrapper around LightGBM."""

    def __init__(self, n_classes: int = 2, n_estimators: int = 400,
                 max_depth: int = 8, learning_rate: float = 0.05,
                 random_state: int = 42):
        self.n_classes    = n_classes
        self.n_estimators = n_estimators
        self.max_depth    = max_depth
        self.learning_rate= learning_rate
        self.random_state = random_state
        self._model       = None
        self.classes_     = None

    def fit(self, X, y):
        import lightgbm as lgb
        self.classes_  = np.unique(y)
        nc = len(self.classes_)
        label_map = {c: i for i, c in enumerate(self.classes_)}
        y_mapped  = np.array([label_map[yi] for yi in y])
        self._label_map    = label_map
        self._inv_label_map = {v: k for k, v in label_map.items()}
        params = {
            "objective":      "multiclass" if nc > 2 else "binary",
            "num_class":      nc if nc > 2 else 1,
            "max_depth":      self.max_depth,
            "learning_rate":  self.learning_rate,
            "n_estimators":   self.n_estimators,
            "num_leaves":     63,
            "subsample":      0.8,
            "colsample_bytree": 0.8,
            "n_jobs":         N_CORES,
            "random_state":   self.random_state,
            "verbose":        -1,
        }
        self._model = lgb.LGBMClassifier(**params)
        self._model.fit(X, y_mapped)
        self.classes_ = np.array(self.classes_)
        return self

    def predict(self, X):
        idx = self._model.predict(X)
        return np.array([self._inv_label_map[i] for i in idx])

    def predict_proba(self, X):
        p = self._model.predict_proba(X)
        if p.shape[1] == 1:
            return np.hstack([1 - p, p])
        return p

    @property
    def feature_importances_(self):
        return self._model.feature_importances_ if self._model else np.array([])


def make_activity_classifier(n_classes: int = 6) -> object:
    """Return best available activity classifier."""
    if "xgboost" in BACKEND:
        return XGBWrapper(
            n_classes=n_classes, n_estimators=500,
            max_depth=8, learning_rate=0.05,
            use_gpu=("gpu" in BACKEND),
        )
    if "lightgbm" in BACKEND:
        return LGBMWrapper(n_classes=n_classes, n_estimators=500, max_depth=8)

    from sklearn.ensemble import RandomForestClassifier
    return RandomForestClassifier(
        n_estimators=300, max_depth=14,
        min_samples_leaf=2, n_jobs=-1, random_state=42,
    )


def make_type_classifier(n_classes: int = 12) -> object:
    """Return best available vessel-type classifier."""
    if "xgboost" in BACKEND:
        return XGBWrapper(
            n_classes=n_classes, n_estimators=400,
            max_depth=7, learning_rate=0.05,
            use_gpu=("gpu" in BACKEND),
        )
    if "lightgbm" in BACKEND:
        return LGBMWrapper(n_classes=n_classes, n_estimators=400, max_depth=7)

    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(
        n_estimators=200, max_depth=5,
        learning_rate=0.08, random_state=42,
    )
