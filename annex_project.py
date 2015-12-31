import os, json
from sys import argv, exit
from subprocess import Popen

from dutils.conf import BASE_DIR, DUtilsKeyDefaults, load_config, build_config, save_config, append_to_config
from dutils.dutils import build_dockerfile, generate_init_routine

CONTAINER_TMPL = ["instal.sh", "run.sh"]
PROJECT_TMPL = ["unveillance.sh", "setup.sh", "vars.json"]

class AnnexProject():
	def __init__(self, config=None):
		if config is not None:
			self.config = load_config(with_config=config)

	def initialize(self):
		# this only creates the base image; can be updated/cloned later
		base_config_tmpl = os.path.join(BASE_DIR, "tmpl", "docker.tmpl.json")
		base_config = os.path.join(BASE_DIR, "docker.config.json")

		config_keys = [
			DUtilsKeyDefaults['USER_PWD']
		]

		self.config = build_config(config_keys, with_config=base_config_tmpl)
		save_config(self.config, with_config=base_config)

		from dutils.dutils import get_docker_exe, get_docker_ip

		res, self.config = append_to_config({
			'DOCKER_EXE' : get_docker_exe(),
			'DOCKER_IP' : get_docker_ip()
		}, return_config=True, with_config=base_config)

		# add configs
		with open(os.path.join(BASE_DIR, "src", "unveillance.secrets.json"), 'wb+') as u:
			u.write(json.dumps(self.config['ANNEX_CONFIG']))

		# build Dockerfile and routine
		dockerfile = os.path.join(BASE_DIR, "tmpl", "Dockerfile.init")
		return build_dockerfile(dockerfile, self.config) and \
			generate_init_routine(self.config, with_config=base_config)

	def build(self):
		return False

	def commit(self):
		return False

	def update(self):
		return False

if __name__ == "__main__":
	res = False
	annex_project = AnnexProject(None if len(argv) == 2 else argv[2])

	options = {
		"init" : annex_project.initialize,
		"build" : annex_project.build,
		"commit" : annex_project.commit,
		"update" : annex_project.update
	}

	try:
		res = options[argv[1]]()
	except Exception as e:
		print e, type(e)

	exit(0 if res else -1)