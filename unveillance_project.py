import os, json
from sys import argv, exit

from dutils.conf import BASE_DIR, DUtilsKeyDefaults, load_config, build_config, save_config, append_to_config
from dutils.dutils import build_dockerfile, generate_init_routine, generate_build_routine, build_routine

CONTAINER_TMPL = ["instal.sh", "run.sh"]
PROJECT_TMPL = ["unveillance.sh", "setup.sh", "vars.json"]
FIRST_ALLOCATION = 9000

class AnnexProject():
	def __init__(self, image_home):
		if image_home is not None:
			self.config = load_config(with_config=os.path.join(image_home, "docker.config.json"))
			self.config['IMAGE_HOME'] = image_home

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

		# build Dockerfile and routine
		dockerfile = os.path.join(BASE_DIR, "tmpl", "Dockerfile.init")
		return build_dockerfile(dockerfile, self.config) and \
			generate_init_routine(self.config, with_config=base_config)

	def build(self):
		config_path = os.path.join(self.config['IMAGE_HOME'], "docker.config.json")
		base_config = load_config(with_config=os.path.join(BASE_DIR, "docker.config.json"))
		
		self.config.update(base_config)
		save_config(self.config, with_config=config_path)

		# allocate published ports
		allocations_manifest = os.path.join(BASE_DIR, "docker.allocations.txt")
		
		last_allocation = FIRST_ALLOCATION - 1

		if os.path.exists(allocations_manifest):
			from fabric.api import settings, local
			with settings(warn_only=True):
				last_allocation = int(local("tail -n 1 %s" % allocations_manifest, capture=True).split(" ")[-1])

		# add frontend configs
		frontend_config = load_config(with_config=os.path.join(BASE_DIR, "tmpl", "frontend.tmpl.json"))
		frontend_config.update({
			'server_host': self.config['DOCKER_IP'],
			'server_port': last_allocation + 1,
			'server_message_port': last_allocation + 2,
			'annex_remote_port' : last_allocation + 3,
			'api.port': last_allocation + 4,	#whatever's available on host
			'annex_local' : os.path.join(self.config['IMAGE_HOME'], "data"),
			'ssh_root' : os.path.join(os.path.expanduser("~"), ".ssh")
		})

		# establish PUBLISH_DIRECTIVES for server ports
		publish_directives = {
			"%s" % str(self.config['API_PORT']) : frontend_config['server_port'],
			"%s" % str(self.config['MESSAGE_PORT']) : frontend_config['server_message_port'],
			"22" : frontend_config['annex_remote_port']
		}

		publish_directives_str = ["-p %s:%s" % (str(publish_directives[k]), k) for k in publish_directives.keys()]

		# persist everything
		with open(os.path.join(self.config['IMAGE_HOME'], "unveillance.secrets.json"), 'wb+') as u:
			u.write(json.dumps(frontend_config))

		with open(allocations_manifest, 'ab') as u:
			u.write("%s\n" % " ".join([str(frontend_config[c]) for c in \
				['server_port', 'server_message_port', 'annex_remote_port', 'api.port']]))

		res, self.config = append_to_config({
			"DEFAULT_PORTS" : " ".join(publish_directives.keys()),
			"PROJECT_NAME" : os.path.split(self.config['IMAGE_HOME'])[1].replace(" ", "-").lower(),
			"PUBLISH_DIRECTIVES" : " ".join(publish_directives_str)
		}, return_config=True, with_config=config_path)

		dockerfile = os.path.join(BASE_DIR, "tmpl", "Dockerfile.build")
		return build_dockerfile(dockerfile, self.config, dst=self.config['IMAGE_HOME']) and \
			generate_build_routine(self.config, dst=self.config['IMAGE_HOME'])

	def commit(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())
		
		# add remaining frontend templates
		# write git_as.sh and ssh_as.sh
		ssh_cmd = ['exec ssh -i %(ssh_key_priv)s -o PubkeyAuthentication=yes -o IdentitiesOnly=yes "$@"' % frontend_config]
		git_cmd = ['GIT_SSH=%s/ssh_as.sh exec git "$@"' % self.config['IMAGE_HOME']]

		for c in [("git_as", git_cmd), ("ssh_as", ssh_cmd)]:
			with open(os.path.join(self.config['IMAGE_HOME'], "%s.sh" % c[0]), 'wb+') as g:
				g.write("#! /bin/bash")
				g.write("\n")
				g.write("\n".join(c[1]))

		# say hello to annex
		# git remote add docker image
		routine = [
			"chmod +x %(IMAGE_HOME)s/*.sh" % self.config,
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'echo \"\"'" % frontend_config,
			"cd %(IMAGE_HOME)s/annex" % self.config,
			"git config alias.unveillance \\!\"%(IMAGE_HOME)s/git_as.sh\"" % self.config,
			"git remote add origin ssh://%(server_user)s@localhost:%(annex_remote_port)d/~/unveillance" % frontend_config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])
		
	def update(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'cd ~/unveillance && git reset --hard HEAD && cd lib/Annex && ./update.sh all'" % frontend_config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def start(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"%(DOCKER_EXE)s start %(PROJECT_NAME)s" % self.config,
			"sleep 3",
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes \
				-i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'source ~/.bash_profile && cd ~/unveillance/lib/Annex && ./startup.sh'" % frontend_config
		]
		
		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def stop(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes \
				-i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'source ~/.bash_profile && cd ~/unveillance/lib/Annex && ./shutdown.sh'" % frontend_config,
			"sleep 3",
			"%(DOCKER_EXE)s stop %(PROJECT_NAME)s" % self.config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def remove(self):
		routine = [
			"%(DOCKER_EXE)s stop %(PROJECT_NAME)s",
			"%(DOCKER_EXE)s rm %(PROJECT_NAME)s",
			"%(DOCKER_EXE)s rmi %(IMAGE_NAME)s:%(PROJECT_NAME)s",
			"cd ../",
			"rm -rf %(IMAGE_HOME)s"
		]

		return build_routine([r % self.config for r in routine], dst=self.config['IMAGE_HOME'])

if __name__ == "__main__":
	res = False
	annex_project = AnnexProject(None if len(argv) == 2 else argv[2])

	options = {
		"init" : annex_project.initialize,
		"build" : annex_project.build,
		"commit" : annex_project.commit,
		"update" : annex_project.update,
		"start" : annex_project.start,
		"stop" : annex_project.stop,
		"remove" : annex_project.remove
	}

	try:
		res = options[argv[1]]()
	except Exception as e:
		print e, type(e)

	if type(res) is bool:
		exit(0 if res else -1)
	elif type(res) in [str, unicode]:
		exit(res)

	exit(-1)