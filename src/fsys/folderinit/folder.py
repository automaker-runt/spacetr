# Folder
import os

class Folder():

	os_projver_folderpath = os.path.dirname(__file__)+"/../.."
	os_proj_folderpath = os.path.dirname(__file__)+"/../../.."
	src = os.path.dirname(__file__)+"/"

	@classmethod
	def get_folder_content(cls, folder, filesonly:bool=False, pyonly:bool=False):
		if not filesonly and not pyonly:
			# need all the folder content, all files, all folders
			return os.listdir(folder)
		else:
			folder_files = list()			

			# just need all filenames
			if filesonly and not pyonly:
				for file in os.listdir(folder):
					if file.find(".") > -1:
						folder_files.append(file)

				return folder_files

			# need all py files, without the ".py" ending
			elif pyonly and not filesonly:
				for item in os.listdir(folder):
					# filter for folders that are not the __pycache__ folder
					if item.find(".") == -1 and item != "__pycache__":
						folder_files.append(item)
					# filter for files that are too short, don't have .py or
					# are the __init__.py file
					elif any([len(item) <= 3, item[-3:] != ".py", item == "__init__.py"]):
						continue
					else:
						folder_files.append(item[:-3])

				return folder_files

			# if none condition met, raise for false combination
			else:
				raise Exception(f"Invalid parameter combination filesonly={filesonly} and pyonly={pyonly}")
