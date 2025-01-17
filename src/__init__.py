import os
from src.fsys.folderinit.folder import Folder

__all__ = Folder.get_folder_content(os.path.dirname(__file__), pyonly=True)


# import pkgutil

# __all__ = []
# for loader, module_name, is_pkg in pkgutil.walk_packages(__path__):
#     __all__.append(module_name)
#     _module = loader.find_module(module_name).load_module(module_name)
#     globals()[module_name] = _module



