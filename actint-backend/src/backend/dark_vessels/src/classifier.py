"""
Activity Intelligence Classifier

Two-level classification:
  Level 1 – Vessel type inference (when vessel_type_code is absent / spoofed)
  Level 2 – Activity classification (fishing / transit / anchored / loitering / STS)

Also includes:
  - Dark-vessel risk scoring
  - IUU (Illegal, Unreported, Unregulated) fishing risk scoring
  - Sanctions-evasion STS risk scoring
"""

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import cross_val_score
from sklearn.metrics import classification_report, confusion_matrix
from typing import Tuple
from .gpu_utils import make_activity_classifier, make_type_classifier, BACKEND, compute_device


# ---------------------------------------------------------------------------
# Feature columns
# ---------------------------------------------------------------------------

ACTIVITY_FEATURES = [
    "sog_mean", "sog_std", "sog_max",
    "pct_slow", "pct_vslow", "pct_fast",
    "cog_std", "zig_zag", "mean_turning_rate", "max_turning_rate",
    "loiter_index",
    "lat_range", "lon_range", "total_dist_nm", "bbox_area",
    "pct_fishing_status", "pct_anchored_status",
    "n_dark_gaps", "max_dark_gap_h", "pct_dark",
    "length", "draught",
    "dist_to_port_nm", "dist_to_fishing_nm",
    "t_span_h", "n_pings",
    # Geo-contextual priors (from GeoFeatureAugmenter; NaN if not augmented)
    "gfw_effort",      # GFW fishing effort density [0,1] at segment centroid
    "lane_proximity",  # proximity to major shipping lanes [0,1]
    "gear_depth_fit",  # bathymetric depth match for fishing gear [0,1]
]

VESSEL_TYPE_FEATURES = [
    "sog_mean", "sog_max", "sog_std",
    "length", "draught",
    "pct_slow", "pct_fast",
    "cog_std", "zig_zag",
    "total_dist_nm", "bbox_area",
]


# ---------------------------------------------------------------------------
# Activity label mapping
# ---------------------------------------------------------------------------

ACTIVITY_LABELS = {
    "fishing":       "Fishing",
    "transit":       "Transit",
    "anchored":      "Anchored/Moored",
    "loiter":        "Loitering",
    "sts":           "STS Transfer",
    "port":          "In Port",
    "transshipment": "Transshipment at Sea",
    "bunkering":     "Bunkering",
    "survey":        "Survey / Research",
    "patrol_sweep":  "Patrol / SAR Sweep",
    "dredging":      "Dredging",
}

VESSEL_TYPE_LABELS = {
    # Simulator types
    "trawler":        "Fishing - Trawler",
    "longliner":      "Fishing - Longliner",
    "purse_seiner":   "Fishing - Purse Seiner",
    "bulk_carrier":   "Bulk Carrier",
    # Real AIS / unified types
    "fishing":        "Fishing",
    "cargo":          "Cargo",
    "tanker":         "Tanker",
    "passenger":      "Passenger",
    "tug":            "Tug / Towing",
    "naval":          "Naval / Law Enforcement",
    "support_vessel": "Support / SAR / Pilot",
    "sailing":        "Sailing Vessel",
    "pleasure_craft": "Pleasure Craft",
    "hsc":            "High-Speed Craft",
    "other":          "Other",
}


# ---------------------------------------------------------------------------
# Classifier class
# ---------------------------------------------------------------------------

class ActivityIntelligenceClassifier:

    def __init__(self):

    # This decides between using XGBoost, LGBMWrapper, and RandomForestClassifier which are all similar python packages for making decisoin trees. It will pick depending on what is on your computer.
        self.activity_clf   = make_activity_classifier(n_classes=len(ACTIVITY_LABELS))
        
    # Similar to self.activity_clf, but has some different parameters to be used for vessel type classification.
        self.vessel_clf     = make_type_classifier(n_classes=len(VESSEL_TYPE_LABELS))

        # This encodes strings/labels as numbers and has a couple methods that can classify labels, count the number of each label and inverse classify them (get the label from the number.)
        self.activity_enc   = LabelEncoder()
        self.vessel_enc     = LabelEncoder()
        self._trained       = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    # This essentially adds the vessel features matched with the vessels and seperately, activity features matched with the true activity.
    def fit(self, feat_df: pd.DataFrame) -> "ActivityIntelligenceClassifier":
        
        """Train on feature DataFrame (must include true_activity and vessel_type_key)."""
        feat_df = feat_df.dropna(subset=["true_activity", "vessel_type_key"])

        # Activity model
        # Selects all vessels with a true activity, and extracts their features and true activities
        act_mask = feat_df["true_activity"].isin(ACTIVITY_LABELS)
        X_act = feat_df.loc[act_mask, ACTIVITY_FEATURES].fillna(0).values
        y_act = feat_df.loc[act_mask, "true_activity"].values
        
        if len(X_act) > 0:

            # This is where the training loop is. Adds the labels and features to the model.
            self.activity_clf.fit(X_act, y_act)
            # Keep LabelEncoder in sync for evaluate()
            self.activity_enc.fit(y_act)

        # Vessel type model

        # selects the vessel type features and vessel type values for all the vessles.
        vt_mask = feat_df["vessel_type_key"].isin(VESSEL_TYPE_LABELS)
        X_vt = feat_df.loc[vt_mask, VESSEL_TYPE_FEATURES].fillna(0).values
        y_vt = feat_df.loc[vt_mask, "vessel_type_key"].values
        if len(X_vt) > 0:
            self.vessel_clf.fit(X_vt, y_vt)
            self.vessel_enc.fit(y_vt)

        self._trained = True
        return self

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        if not self._trained:
            raise RuntimeError("Call fit() before predict()")

        X_act = feat_df[ACTIVITY_FEATURES].fillna(0).values
        X_vt  = feat_df[VESSEL_TYPE_FEATURES].fillna(0).values

        act_preds = self.activity_clf.predict(X_act)       # string labels
        act_prob  = self.activity_clf.predict_proba(X_act)
        vt_preds  = self.vessel_clf.predict(X_vt)
        vt_prob   = self.vessel_clf.predict_proba(X_vt)

        results = feat_df[["mmsi", "name", "flag"]].copy().reset_index(drop=True)
        results["pred_activity"]       = act_preds
        results["activity_confidence"] = act_prob.max(axis=1)
        results["pred_vessel_type"]    = vt_preds
        results["vessel_confidence"]   = vt_prob.max(axis=1)

        # Activity probability breakdown
        act_classes = self.activity_clf.classes_
        for i, cls in enumerate(act_classes):
            if i < act_prob.shape[1]:
                results[f"prob_{cls}"] = act_prob[:, i]

        # Risk scores
        results["dark_vessel_risk"]      = self._dark_risk(feat_df)             # The risk of going dark, this is not computed using AI, it is just math.
        results["iuu_fishing_risk"]      = self._iuu_risk(feat_df, results)     # These other two are calculated in similar ways. They use the activity identified 
        results["sts_evasion_risk"]      = self._sts_risk(feat_df, results)     # by the AI model and then use those to determine if they could beillegally fishing or if they havea high probability of going dark and whatever.
                                                                                # STS is ship to ship risk (or rendesvous risk)
        results["overall_anomaly_score"] = results[
            ["dark_vessel_risk", "iuu_fishing_risk", "sts_evasion_risk"]
        ].max(axis=1)

        # Human-readable label
        results["pred_activity_label"] = results["pred_activity"].map(
            lambda x: ACTIVITY_LABELS.get(x, x))
        results["pred_vessel_label"]   = results["pred_vessel_type"].map(
            lambda x: VESSEL_TYPE_LABELS.get(x, x))

        return results

    # ------------------------------------------------------------------
    # Risk scoring
    # ------------------------------------------------------------------

    def _dark_risk(self, df: pd.DataFrame) -> pd.Series:
        """0-1 score for likelihood that vessel is intentionally going dark."""
        score = (
            np.clip(df["n_dark_gaps"] / 5, 0, 1) * 0.4 +
            np.clip(df["max_dark_gap_h"] / 12, 0, 1) * 0.35 +
            np.clip(df["pct_dark"] * 3, 0, 1) * 0.25
        )
        return score.clip(0, 1)

    def _iuu_risk(self, df: pd.DataFrame, results: pd.DataFrame) -> pd.Series:
        """Risk of illegal / unreported fishing."""
        is_fishing = (results["pred_activity"] == "fishing").astype(float)
        far_from_ground = np.clip((df["dist_to_fishing_nm"] - 50) / 200, 0, 1)
        dark_bonus = np.clip(df["pct_dark"] * 5, 0, 1)
        suspicious_flag = df["flag"].isin(
            ["VU", "PA", "SL", "KM", "TG", "GN", "GQ"]).astype(float) * 0.3

        score = is_fishing * (0.35 + far_from_ground * 0.25 + dark_bonus * 0.30) + suspicious_flag
        return score.clip(0, 1)

    def _sts_risk(self, df: pd.DataFrame, results: pd.DataFrame) -> pd.Series:
        """Risk of sanctions-evading ship-to-ship transfer."""
        is_sts   = (results["pred_activity"] == "sts").astype(float)
        is_tanker = results["pred_vessel_type"].isin(["tanker"]).astype(float)
        dark_sts  = df["pct_dark"] * is_tanker
        remote    = np.clip((df["dist_to_port_nm"] - 100) / 400, 0, 1)

        score = is_sts * 0.5 + dark_sts * 0.3 + remote * 0.2 * is_tanker
        return score.clip(0, 1)

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(self, feat_df: pd.DataFrame) -> dict:
        if not self._trained:
            raise RuntimeError("Call fit() before evaluate()")

        feat_df = feat_df.dropna(subset=["true_activity"])
        known_labels = set(self.activity_clf.classes_)
        act_mask = feat_df["true_activity"].isin(known_labels)
        if act_mask.sum() < 5:
            return {}
        X      = feat_df.loc[act_mask, ACTIVITY_FEATURES].fillna(0).values
        y_true = feat_df.loc[act_mask, "true_activity"].values
        y_pred = self.activity_clf.predict(X)   # returns string labels

        present = sorted(set(y_true) | set(y_pred))
        report  = classification_report(
            y_true, y_pred, labels=present,
            target_names=present, output_dict=True, zero_division=0,
        )
        cm = confusion_matrix(y_true, y_pred, labels=present)
        fi = pd.Series(
            self.activity_clf.feature_importances_,
            index=ACTIVITY_FEATURES
        ).sort_values(ascending=False)

        return {
            "classification_report": report,
            "confusion_matrix": cm,
            "feature_importance": fi,
            "labels": present,
        }

    def cross_validate(self, feat_df: pd.DataFrame, cv: int = 5) -> dict:
        """Return cross-validated accuracy scores."""
        act_mask = feat_df["true_activity"].isin(ACTIVITY_LABELS)
        X = feat_df.loc[act_mask, ACTIVITY_FEATURES].fillna(0)
        y = self.activity_enc.transform(feat_df.loc[act_mask, "true_activity"])
        scores = cross_val_score(self.activity_clf, X, y, cv=cv, scoring="f1_weighted")
        return {"cv_f1_scores": scores, "mean_f1": scores.mean(), "std_f1": scores.std()}
