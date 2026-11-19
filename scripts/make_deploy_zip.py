"""Package source at ZIP root for Azure deployment, omitting credentials/state."""
from pathlib import Path
import argparse
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=ROOT/"build"/"app-deploy.zip")
    args=parser.parse_args()
    dest=args.output.resolve();dest.parent.mkdir(parents=True,exist_ok=True)
    allowed=["presentation_search","scripts","integrations","data/presentations","pyproject.toml","requirements.txt"]
    with zipfile.ZipFile(dest,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        for name in allowed:
            item=ROOT/name
            candidates=[item] if item.is_file() else sorted(item.rglob("*"))
            for path in candidates:
                if not path.is_file() or "__pycache__" in path.parts or path.suffix==".pyc" or path.is_symlink():
                    continue
                archive.write(path,path.relative_to(ROOT).as_posix())
    print(dest)
if __name__=="__main__":
    main()
