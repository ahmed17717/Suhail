"""Download the embedding model and LLM weights (run once, on a machine with internet).

    python -m scripts.download_models
    python -m scripts.download_models --skip-llm

Then copy the project's `models/` folder to the air-gapped server and keep
HF_HUB_OFFLINE=1 in its .env so nothing ever tries to reach the internet.
"""

from __future__ import annotations

import argparse
import os

DEFAULT_LLM_REPO = "bartowski/Qwen2.5-14B-Instruct-GGUF"  # ships the single-file Q4_K_M


def main() -> int:
    from scripts._common import load_settings

    settings = load_settings()

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--llm-repo", default=DEFAULT_LLM_REPO)
    parser.add_argument("--skip-llm", action="store_true", help="only fetch the embedding model")
    parser.add_argument("--skip-embedding", action="store_true", help="only fetch the LLM")
    args = parser.parse_args()

    # Downloading is the one operation that needs the network.
    os.environ["HF_HUB_OFFLINE"] = "0"
    from huggingface_hub import hf_hub_download, snapshot_download

    if not args.skip_embedding:
        repo = settings.embedding_model
        if "/" not in repo:
            repo = f"sentence-transformers/{repo}"
        print(f"Downloading embedding model {repo} ...")
        snapshot_download(repo_id=repo)

    if not args.skip_llm:
        target = settings.llm_model_path
        target.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {target.name} from {args.llm_repo} (~9 GB) ...")
        hf_hub_download(repo_id=args.llm_repo, filename=target.name, local_dir=target.parent)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
