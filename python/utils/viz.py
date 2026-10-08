import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from utils.config import FIGURES_DIR

sns.set_theme(style="whitegrid", palette="deep", font="DejaVu Sans")
PALETTE = ["#1f6feb", "#0ca678", "#f76707", "#e64980", "#7950f2", "#adb5bd", "#f59f00", "#12b886"]
plt.rcParams.update({
    "figure.dpi": 120,
    "savefig.dpi": 150,
    "axes.titleweight": "bold",
    "axes.titlesize": 12,
    "grid.alpha": 0.35,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / name, bbox_inches="tight")
    plt.close(fig)
    print(f"  saved report/figures/{name}")
    return FIGURES_DIR / name