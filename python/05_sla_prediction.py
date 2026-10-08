import json
import joblib
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             roc_auc_score, roc_curve, confusion_matrix,
                             classification_report)
from utils.config import DATA_PROCESSED, REPORT_DIR
from utils.viz import save

df = pd.read_csv(DATA_PROCESSED / "analysis_features.csv")
res = df[df.status == "Closed"].copy()
res["target"] = res.sla_breach.astype(int)

cat_cols = ["priority", "category", "department", "channel", "customer_segment", "agent_shift"]
num_cols = ["agent_load", "n_escalations", "sla_hours", "response_sla_hours",
            "time_of_day", "day_of_week", "is_night", "is_weekend"]
X = res[cat_cols + num_cols]
y = res.target

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25,
                                                    random_state=42, stratify=y)

prep = ColumnTransformer([("num", StandardScaler(), num_cols),
                          ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols)])

models = {
    "Logistic Regression": LogisticRegression(max_iter=2000, class_weight="balanced"),
    "Random Forest": RandomForestClassifier(n_estimators=250, max_depth=14,
                                            min_samples_leaf=20, n_jobs=-1,
                                            class_weight="balanced", random_state=42),
}

print(f"Training on {len(X_train):,} / testing {len(X_test):,} rows; positive rate {y.mean():.3f}")
results = {}
fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
ax1, ax2 = axes
for name, model in models.items():
    pipe = Pipeline([("prep", prep), ("model", model)])
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]
    pred = pipe.predict(X_test)
    cm = confusion_matrix(y_test, pred)
    fpr, tpr, _ = roc_curve(y_test, proba)
    results[name] = dict(
        precision=round(precision_score(y_test, pred), 3),
        recall=round(recall_score(y_test, pred), 3),
        f1=round(f1_score(y_test, pred), 3),
        roc_auc=round(roc_auc_score(y_test, proba), 3),
        tn=int(cm[0, 0]), fp=int(cm[0, 1]), fn=int(cm[1, 0]), tp=int(cm[1, 1]),
    )
    ax1.plot(fpr, tpr, lw=2, label=f"{name} (AUC {results[name]['roc_auc']:.3f})")
    print(f"\n== {name} ==")
    print(f"  precision {results[name]['precision']:.3f} | recall {results[name]['recall']:.3f}"
          f" | f1 {results[name]['f1']:.3f} | roc-auc {results[name]['roc_auc']:.3f}")
    print("  confusion matrix [[TN FP][FN TP]]:\n", cm)

ax1.plot([0, 1], [0, 1], "--", color="gray", alpha=0.5)
ax1.set_xlabel("False positive rate"); ax1.set_ylabel("True positive rate")
ax1.set_title("ROC — SLA breach prediction"); ax1.legend(loc="lower right")

rf = Pipeline([("prep", prep), ("model", models["Random Forest"])])
rf.fit(X_train, y_train)
cat_names = prep.named_transformers_["cat"].get_feature_names_out(cat_cols).tolist()
feat_names = num_cols + cat_names
importances = pd.Series(rf.named_steps["model"].feature_importances_, index=feat_names).sort_values(ascending=False)
importances.head(15).reset_index(name="importance").to_csv(DATA_PROCESSED / "feature_importance.csv", index=False)
imp = importances.head(15)[::-1]
imp.plot(kind="barh", ax=ax2, color="#1f6feb")
ax2.set_xlabel("Gini importance"); ax2.set_title("Top drivers of SLA breach (Random Forest)")
save(fig, "05_roc_and_importance.png")

print("\nfeature importance (top 10):")
print(importances.head(10).round(4).to_string())

joblib.dump(rf, DATA_PROCESSED / "model_rf.joblib")
joblib.dump(dict(cat_cols=cat_cols, num_cols=num_cols), DATA_PROCESSED / "model_meta.joblib")
pd.DataFrame({"columns": X.columns}).to_csv(DATA_PROCESSED / "model_columns.csv", index=False)

report = dict(
    train_size=len(X_train), test_size=len(X_test), positive_rate=round(float(y.mean()), 4),
    results=results,
    top_features=importances.head(15).round(4).to_dict(),
)
(REPORT_DIR / "sla_model_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("\nSaved model artifacts + report/sla_model_report.json")