import os
import shutil
import subprocess
from pathlib import Path
import pytest
from runnrr.core.filesystem import init_runnrr, RUNNRR_ROOT

def test_init_with_parent_git(tmp_path):
    """Test runnrr init in a temp dir with a parent .git/ -> .gitignore gets .runnrr/ added."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".git").mkdir()
    
    subdir = project_root / "subdir"
    subdir.mkdir()
    
    # Change CWD to subdir for the test
    old_cwd = os.getcwd()
    os.chdir(subdir)
    try:
        init_runnrr(subdir)
        
        gitignore = project_root / ".gitignore"
        assert gitignore.exists()
        assert f"{RUNNRR_ROOT}/" in gitignore.read_text()
    finally:
        os.chdir(old_cwd)

def test_init_no_duplicate_gitignore(tmp_path):
    """Test runnrr init when .runnrr/ already in .gitignore -> no duplicate entry added."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / ".git").mkdir()
    gitignore = project_root / ".gitignore"
    gitignore.write_text(f"{RUNNRR_ROOT}/\n", encoding="utf-8")
    
    old_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        init_runnrr(project_root)
        
        content = gitignore.read_text()
        assert content.count(f"{RUNNRR_ROOT}/") == 1
    finally:
        os.chdir(old_cwd)

def test_init_no_git_no_error(tmp_path):
    """Test runnrr init with no .git/ anywhere in the tree -> no error."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    old_cwd = os.getcwd()
    os.chdir(project_root)
    try:
        # Should not raise any error
        init_runnrr(project_root)
        assert (project_root / RUNNRR_ROOT).exists()
    finally:
        os.chdir(old_cwd)

def test_no_gitpython_imports():
    """Test that gitpython is never imported in the codebase."""
    src_root = Path(__file__).parent.parent / "src"
    
    # Use grep-like search in python
    forbidden = ["gitpython", "GitIntegration", "Repo("]
    found = []
    
    for path in src_root.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        for term in forbidden:
            if term in content:
                found.append(f"{path}: {term}")
                
    assert not found, f"Forbidden git-related terms found: {found}"

def test_init_in_nested_subdir(tmp_path):
    """Test runnrr init in a deep subdirectory of a git repo."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    
    deep_dir = repo_root / "a" / "b" / "c"
    deep_dir.mkdir(parents=True)
    
    old_cwd = os.getcwd()
    os.chdir(deep_dir)
    try:
        init_runnrr(deep_dir)
        
        gitignore = repo_root / ".gitignore"
        assert gitignore.exists()
        assert f"{RUNNRR_ROOT}/" in gitignore.read_text()
    finally:
        os.chdir(old_cwd)
