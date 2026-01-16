from pathlib import Path

def next_available_filename(base):
  """
  Find the next available filename by appending (1), (2), etc. before the file extension.
  
  :param base: file path to start from
  """
  base = Path(base)
  if not base.exists():
    return base

  stem = base.stem
  suffix = base.suffix
  parent = base.parent

  i = 1
  while True:
    candidate = parent / f"{stem} ({i}){suffix}"
    if not candidate.exists():
      return candidate
    i += 1