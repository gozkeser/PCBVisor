import argparse
import os
import zipfile
from pathlib import Path

AUTHOR = "G.OZKESER"
VERSION = "1.00"
LAST_UPDATE_DATE = "14.07.2026"

def create_zip(source_path, dest_zip):
    """Zips a directory or file."""
    source_path = Path(source_path)
    if not source_path.exists():
        print(f"Error: Source path '{source_path}' does not exist.")
        return False
        
    if not dest_zip:
        dest_zip = f"{source_path}.zip"
    
    if Path(dest_zip).exists():
        response = input(f"Warning: The file '{dest_zip}' already exists. Overwriting it will destroy its current contents! Do you want to continue? (y/N): ")
        if response.strip().lower() not in ['y', 'yes']:
            print("Operation cancelled by user.")
            return False
            
    print(f"Creating zip archive: {dest_zip}")
    try:
        with zipfile.ZipFile(dest_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if source_path.is_file():
                zipf.write(source_path, source_path.name)
            elif source_path.is_dir():
                for root, dirs, files in os.walk(source_path):
                    for file in files:
                        file_path = Path(root) / file
                        arcname = file_path.relative_to(source_path)
                        zipf.write(file_path, arcname)
        return True
    except Exception as e:
        print(f"Failed to create zip: {e}")
        return False

def add_to_zip(file_to_add, dest_zip):
    """Adds a file to an existing zip archive."""
    if not dest_zip:
        print("Error: Destination zip file must be provided with --to")
        return False
        
    file_path = Path(file_to_add)
    if not file_path.exists():
        print(f"Error: File to add '{file_to_add}' does not exist.")
        return False
        
    if not Path(dest_zip).exists():
        print(f"Error: Destination zip '{dest_zip}' does not exist.")
        return False
    
    print(f"Adding '{file_to_add}' to '{dest_zip}'")
    try:
        with zipfile.ZipFile(dest_zip, 'a', zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(file_to_add, file_path.name)
        return True
    except Exception as e:
        print(f"Failed to add file: {e}")
        return False

def remove_from_zip(file_to_remove, source_zip):
    """Removes a file from an existing zip archive."""
    if not source_zip:
        print("Error: Source zip file must be provided with --from")
        return False
        
    if not Path(source_zip).exists():
        print(f"Error: Source zip '{source_zip}' does not exist.")
        return False
    
    # Normalize path for zip format (always uses forward slash and no leading dot)
    normalized_file = file_to_remove.replace('\\', '/')
    if normalized_file.startswith('./'):
        normalized_file = normalized_file[2:]
        
    print(f"Removing '{normalized_file}' from '{source_zip}'")
    temp_zip = f"{source_zip}.temp"
    
    removed = False
    try:
        with zipfile.ZipFile(source_zip, 'r') as zin:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename != normalized_file:
                        zout.writestr(item, zin.read(item.filename))
                    else:
                        removed = True
                        
        if not removed:
            print(f"Warning: '{normalized_file}' was not found in the zip archive.")
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            return False
        
        # Replace original zip with the updated one
        os.replace(temp_zip, source_zip)
        return True
    except Exception as e:
        print(f"Failed to remove file: {e}")
        if os.path.exists(temp_zip):
            os.remove(temp_zip)
        return False

def extract_zip(source_zip, dest_dir):
    """Extracts a zip archive to a directory."""
    if not Path(source_zip).exists():
        print(f"Error: Source zip '{source_zip}' does not exist.")
        return False
        
    if not dest_dir:
        # Extract to a directory named after the zip file (without extension)
        dest_dir = Path(source_zip).stem
    
    print(f"Extracting '{source_zip}' to '{dest_dir}' directory")
    try:
        with zipfile.ZipFile(source_zip, 'r') as zipf:
            zipf.extractall(dest_dir)
        return True
    except Exception as e:
        print(f"Failed to extract zip: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="A versatile command-line utility for managing zip archives.")
    
    # Positional argument for zipping (made optional so other flags can be used standalone)
    parser.add_argument("path", nargs="?", help="Path to the directory or file to zip.")
    
    parser.add_argument("--add", metavar="a file", help="File to add to a zip archive (requires --to).")
    parser.add_argument("--remove", metavar="a file", help="File to remove from a zip archive (requires --from).")
    parser.add_argument("--from", metavar="archive", dest="from_zip", help="Source zip archive (used with --remove).")
    parser.add_argument("--to", metavar="archive", help="Destination file or directory (used with path, --add, or -e).")
    parser.add_argument("-e", "--extract", help="Zip archive to extract.")
    parser.add_argument("-v", "--version", action="version", version=f"Version: {VERSION} | Author: {AUTHOR} | Last Update: {LAST_UPDATE_DATE}")
    
    args = parser.parse_args()
    
    try:
        if args.extract:
            if extract_zip(args.extract, args.to):
                print("Extraction successful.")
            else:
                print("Extraction failed.")
                
        elif args.remove:
            if remove_from_zip(args.remove, args.from_zip):
                print("Removal successful.")
            else:
                print("Removal failed.")
                
        elif args.add:
            if add_to_zip(args.add, args.to):
                print("Addition successful.")
            else:
                print("Addition failed.")
                
        elif args.path:
            if create_zip(args.path, args.to):
                print("Zipping successful.")
            else:
                print("Zipping failed.")
                
        else:
            parser.print_help()
            
    except Exception as e:
        print(f"Unexpected Error: {e}")

if __name__ == "__main__":
    main()
