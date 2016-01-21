from sys import exit, argv

from lib.Frontend.unveillance_frontend import UnveillanceFrontend

class ProjectFrontend(UnveillanceFrontend):
	"""

	Edit/extend main controller here.

	"""

	def __init__(self):
		UnveillanceFrontend.__init__(self)


if __name__ == "__main__":
	project_frontend = ProjectFrontend()

	if len(argv) != 2:
		exit(-1)

	if argv[1] in ["-stop", "-restart"]:
		project_frontend.shutdown()

	if argv[1] in ["-start", "-firstuse", "-restart"]:
		project_frontend.startup()

	exit(0)