import psycopg
import matplotlib.pyplot as plt
import numpy as np
from backend.mcp_servers.adsb.helpers.basic_tools import get_conn


def print_summary_stats(counts: np.ndarray):
    print("\n===== SUMMARY STATISTICS =====")

    print(f"Total Cells:        {len(counts):,}")
    print(f"Min:                {np.min(counts):,.0f}")
    print(f"Max:                {np.max(counts):,.0f}")

    print(f"Mean:               {np.mean(counts):,.2f}")
    print(f"Median:             {np.median(counts):,.2f}")
    print(f"Std Dev:            {np.std(counts):,.2f}")

    print(f"25th Percentile:    {np.percentile(counts, 25):,.2f}")
    print(f"75th Percentile:    {np.percentile(counts, 75):,.2f}")
    print(f"90th Percentile:    {np.percentile(counts, 90):,.2f}")
    print(f"95th Percentile:    {np.percentile(counts, 95):,.2f}")
    print(f"99th Percentile:    {np.percentile(counts, 99):,.2f}")

    # Heavy-tail indicator
    print(f"Mean / Median:      {np.mean(counts) / np.median(counts):,.2f}")

    # Sparsity metrics
    print(f"Cells > 10:         {np.sum(counts > 10):,}")
    print(f"Cells > 100:        {np.sum(counts > 100):,}")
    print(f"Cells > 1,000:      {np.sum(counts > 1000):,}")
    print(f"Cells > 10,000:     {np.sum(counts > 10000):,}")

    print("================================\n")


def fetch_counts() -> np.ndarray:
    with get_conn() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            cur.execute("""
                SELECT traversal_count
                FROM heatmap_h3_res7_routes
            """)
            rows = cur.fetchall()

    if not rows:
        raise ValueError("No data found.")

    return np.array([r["traversal_count"] for r in rows])


def plot_traversal_histogram(count):
    counts = count

    # Log scale x-values
    log_counts = np.log1p(counts)

    plt.figure(figsize=(12, 6))

    plt.hist(
        log_counts,
        bins=100,
        log=True
    )

    plt.xlabel("log1p(traversal_count)")
    plt.ylabel("Frequency (log scale)")
    plt.title("Traversal Count Distribution (Log X + Log Y)")

    plt.grid(True)

    plt.savefig(
        "traversal_histogram_loglog.png",
        dpi=300,
        bbox_inches="tight"
    )

    print("Saved traversal_histogram_log.png")

    plt.close()


def plot_traversal_histogram_raw(count):
    counts = count 

    plt.figure(figsize=(12, 6))

    plt.hist(
        counts,
        bins=100,
        log=True
    )

    plt.xlabel("traversal_count")
    plt.ylabel("Frequency (log scale)")
    plt.title("Raw Traversal Count Distribution (Log Y)")

    plt.grid(True)

    plt.savefig(
        "traversal_histogram_raw_logy.png",
        dpi=300,
        bbox_inches="tight"
    )

    print("Saved traversal_histogram_raw.png")

    plt.close()


if __name__ == "__main__":
    count = fetch_counts()
    
    print_summary_stats(count)
    plot_traversal_histogram_raw(count)
    plot_traversal_histogram(count)