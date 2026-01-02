"""
Diagnose Embedding environment issues
Check Python environment and dependency installation
"""
import sys
from pathlib import Path

print("=" * 60)
print("Embedding Environment Diagnostic Tool")
print("=" * 60)

# 1. Python info
print("\n[1] Python Environment Info:")
print(f"    Python Version: {sys.version}")
print(f"    Python Path: {sys.executable}")
print(f"    Python Path List:")
for i, path in enumerate(sys.path[:5], 1):
    print(f"      {i}. {path}")

# 2. Check sentence-transformers
print("\n[2] Check sentence-transformers:")
try:
    import sentence_transformers
    print(f"    [OK] sentence-transformers installed")
    print(f"    Version: {sentence_transformers.__version__}")
    print(f"    Path: {sentence_transformers.__file__}")
except ImportError as e:
    print(f"    [ERROR] sentence-transformers not installed")
    print(f"    错误: {e}")
    print(f"    解决方案: pip install sentence-transformers")

# 3. Check torch
print("\n[3] Check torch:")
try:
    import torch
    print(f"    [OK] torch installed")
    print(f"    Version: {torch.__version__}")
    print(f"    CUDA Available: {torch.cuda.is_available()}")
except ImportError as e:
    print(f"    [ERROR] torch not installed")
    print(f"    Error: {e}")
    print(f"    Solution: pip install torch")

# 4. Check transformers
print("\n[4] Check transformers:")
try:
    import transformers
    print(f"    [OK] transformers installed")
    print(f"    Version: {transformers.__version__}")
except ImportError as e:
    print(f"    [ERROR] transformers not installed")
    print(f"    错误: {e}")

# 5. Check huggingface_hub
print("\n[5] Check huggingface_hub:")
try:
    import huggingface_hub
    print(f"    [OK] huggingface_hub installed")
    print(f"    Version: {huggingface_hub.__version__}")
except ImportError as e:
    print(f"    [ERROR] huggingface_hub not installed")
    print(f"    错误: {e}")

# 6. Try loading model
print("\n[6] Try loading Embedding model:")
try:
    from sentence_transformers import SentenceTransformer
    print("    Loading BAAI/bge-large-zh-v1.5...")
    print("    (First run needs to download model, may take a few minutes)")
    model = SentenceTransformer('BAAI/bge-large-zh-v1.5')
    print(f"    [OK] Model loaded successfully!")
    print(f"    Model dimension: {model.get_sentence_embedding_dimension()}")
except Exception as e:
    print(f"    [ERROR] Model loading failed")
    print(f"    Error Type: {type(e).__name__}")
    print(f"    Error Message: {e}")
    import traceback
    print(f"\n    Detailed Error:")
    traceback.print_exc()

# 7. Check config file
print("\n[7] Check config file:")
try:
    import os
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        print(f"    [OK] .env file exists: {env_file}")
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines:
                if 'EMBEDDING' in line.upper() and not line.strip().startswith('#'):
                    print(f"      {line.strip()}")
    else:
        print(f"    [ERROR] .env file not found: {env_file}")
except Exception as e:
    print(f"    [ERROR] Failed to check config file: {e}")

# 8. Suggestions
print("\n" + "=" * 60)
print("Diagnosis Complete")
print("=" * 60)

print("\nIf sentence-transformers is not installed, run:")
print("  pip install sentence-transformers")

print("\nIf running in PyCharm, please check:")
print("  1. File -> Settings -> Project -> Python Interpreter")
print("  2. Make sure the Python interpreter matches the terminal")
print("  3. Or run in PyCharm Terminal: pip install sentence-transformers")

print("\nIf model download fails, please check:")
print("  1. Network connection is normal")
print("  2. Sufficient disk space (model is about 1.3GB)")
print("  3. Can access HuggingFace (https://huggingface.co)")

