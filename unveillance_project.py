#!/usr/bin/env python

import os, json, re
from sys import argv, exit
from fabric.operations import prompt
from fabric.api import settings, local
from fabric.context_managers import hide

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
		# write .git_as.sh and .ssh_as.sh
		ssh_cmd = ['exec ssh -i %(ssh_key_priv)s -o PubkeyAuthentication=yes -o IdentitiesOnly=yes "$@"' % frontend_config]
		git_cmd = ['GIT_SSH=%s/.ssh_as.sh exec git "$@"' % self.config['IMAGE_HOME']]

		for c in [("git_as", git_cmd), ("ssh_as", ssh_cmd)]:
			with open(os.path.join(self.config['IMAGE_HOME'], ".%s.sh" % c[0]), 'wb+') as g:
				g.write("#! /bin/bash")
				g.write("\n")
				g.write("\n".join(c[1]))

		# say hello to annex
		# git remote add docker image
		routine = [
			"chmod +x %(IMAGE_HOME)s/.git_as.sh %(IMAGE_HOME)s/.ssh_as.sh" % self.config,
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'echo \"\"'" % frontend_config,
			"cd %(IMAGE_HOME)s/annex" % self.config,
			"git config alias.unveillance \\!\"%(IMAGE_HOME)s/.git_as.sh\"" % self.config,
			"git remote add origin ssh://%(server_user)s@%(server_host)s:%(annex_remote_port)d/~/unveillance" % frontend_config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])
		
	def update(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'source ~/.bash_profile && cd ~/unveillance && git reset --hard HEAD && ./unveillance.sh update'" % frontend_config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def attach(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"ssh -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s" % frontend_config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def start(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"%(DOCKER_EXE)s start %(PROJECT_NAME)s" % self.config,
			"sleep 3",
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'source ~/.bash_profile && cd ~/unveillance && ./unveillance.sh start'" % frontend_config
		]
		
		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def stop(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"ssh -f -p %(annex_remote_port)d -o IdentitiesOnly=yes -o PubkeyAuthentication=yes -i %(ssh_key_priv)s %(server_user)s@%(server_host)s 'source ~/.bash_profile && cd ~/unveillance/lib/Annex && ./shutdown.sh'&" % frontend_config,
			"sleep 3",
			"%(DOCKER_EXE)s stop %(PROJECT_NAME)s" % self.config
		]

		return build_routine(routine, dst=self.config['IMAGE_HOME'])

	def remove(self):
		with open(os.path.join(self.config['IMAGE_HOME'], "gui", "lib", "Frontend", "conf", "unveillance.secrets.json"), 'rb') as u:
			frontend_config = json.loads(u.read())

		routine = [
			"rm %(ssh_key_priv)s %(ssh_key_priv)s.pub" % frontend_config,
			"%(DOCKER_EXE)s stop %(PROJECT_NAME)s",
			"%(DOCKER_EXE)s rm %(PROJECT_NAME)s",
			"%(DOCKER_EXE)s rmi %(IMAGE_NAME)s:%(PROJECT_NAME)s",
			"cd ../",
			"rm -rf %(IMAGE_HOME)s"
		]

		return build_routine([r % self.config for r in routine], dst=self.config['IMAGE_HOME'])

	def __parse_asset(self, args):
		try:
			return { a[0] : a[1] for a in [a.split("=") for a in args] }
		except Exception as e:
			print e, type(e)

		return {}

	def __tr(self, s):
		if re.match(r'^[a-zA-Z]\w*$', s):
			return True

		print "bad regex."
		return False

	def validate(self, *args):
		print args

		def is_applicable(filename):
			if filename == "__init__.py":
				return False

			if re.match(r'.*pyc$', filename):
				return False

			with settings(hide('everything'), warn_only=True):
				if re.match(re.compile("%s:.*[pP]ython\sscript.*" % filename), local("file %s" % filename, capture=True)):
					return True

			return False

		# go through models, modules, tasks
		# pick out asset tags: make sure they exist in vars

		user_files = []

		for d in ["Models", "Modules", "Tasks"]:
			for root, _, files in os.walk(os.path.join(self.config['IMAGE_HOME'], "annex", d)):
				user_files += [os.path.join(root, f) for f in files if is_applicable(os.path.join(root, f))]

		if len(user_files) == 0:
			return True

		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'rb') as M:
			annex_vars = json.loads(M.read())

		if "ASSET_TAGS" not in annex_vars.keys():
			annex_vars['ASSET_TAGS'] = {}

		for f in user_files:			
			with open(f, 'rb') as F:
				for line in F.readlines():
					for short_code in re.findall(".*ASSET_TAGS\[[\'\"](.*)[\'\"]\].*", line):
						if short_code in annex_vars['ASSET_TAGS'].keys():
							continue

						if not self.__tr(short_code):
							continue

						asset_tag = None

						try:
							if args[0][0] == "add_short_code":
								asset_tag = short_code
						except Exception as e:
							pass

						if asset_tag is None:
							asset_tag = prompt("Descriptive string for \"%s\" asset? (i.e. \"json_from_my_annex\")" % short_code)

						if not self.__tr(asset_tag):
							continue

						annex_vars['ASSET_TAGS'][short_code] = asset_tag
		
		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'wb+') as M:
			M.write(json.dumps(annex_vars, indent=4))
		
		return True

	def model(self, *args):
		new_model = self.__parse_asset(args[0])
		new_model['root'] = os.path.join(self.config['IMAGE_HOME'], "annex", "Models")

		if "name" not in new_model.keys():
			new_model['name'] = prompt("New model name: ")

		if not self.__tr(new_model['name']):
			return False

		new_model['path'] = os.path.join(new_model['root'], "%s.py" % new_model['name'])

		routine = [
			"sed 's/NAME_OF_MODEL/%(name)s/g' $UNVEILLANCE_BUILD_HOME/tmpl/annex.model.py > %(path)s"
		]

		return build_routine([r % new_model for r in routine], dst=self.config['IMAGE_HOME'])

	def asset(self, *args):
		new_asset = self.__parse_asset(args[0])

		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'rb') as M:
			annex_vars = json.loads(M.read())

		if "ASSET_TAGS" not in annex_vars.keys():
			annex_vars['ASSET_TAGS'] = {}

		if "name" not in new_asset.keys():
			new_asset['name'] = prompt("New asset name: ")

		if not self.__tr(new_asset['name']):
			return False

		if "short_code" not in new_asset.keys():
			new_asset['short_code'] = prompt("Short code for new mime type %s (i.e. \"my_json\"): " \
				% new_asset['name'])

		if not self.__tr(new_asset['short_code']):
			return False

		annex_vars['ASSET_TAGS'].update({ new_asset['short_code'] : new_asset['name'] })
		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'wb+') as M:
			M.write(json.dumps(annex_vars, indent=4))

		return True

	def task(self, *args):
		new_task = self.__parse_asset(args[0])			
		new_task['root'] = os.path.join(self.config['IMAGE_HOME'], "annex", "Tasks")

		if "name" not in new_task.keys():
			new_task['name'] = prompt("New task name: ")
		
		if not self.__tr(new_task['name']):
			return False
		
		if "dir" not in new_task.keys():
			print "Which group should this task belong to? "
			for _, d, _ in os.walk(new_task['root']):
				if len(d) > 0:
					print "Choose one from these groups:"
					print ", ".join(d)
					print "or create a new one here."
				else:
					print "No groups yet! Create one here."

				break
			
			new_task['dir'] = prompt("Task group: ")

		if not self.__tr(new_task['dir']):
			return False

		new_task['dir'] = new_task['dir'].capitalize()
		
		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'rb') as M:
			annex_vars = json.loads(M.read())

		if "apply" not in new_task.keys():
			new_task['apply'] = False

			print "Apply mime-type to this task?"
			if prompt("Y|n: ") not in ["n", "N"]:
				new_task['apply'] = "mime_type"
			else:
				print "Run task at project start?"
				if prompt("Y|n: ") not in ["n", "N"]:
					new_task['apply'] = "init"

		if new_task['apply'] == "mime_type":
			for m in ["MIME_TYPES", "MIME_TYPE_MAP", "MIME_TYPE_TASKS"]:
				if m not in annex_vars.keys():
					annex_vars[m] = {}

			if "mime_type" not in new_task.keys():
				if len(annex_vars['MIME_TYPES'].keys()) > 0:
					print "Choose from one of these mime types"
					print ", ".join(annex_vars['MIME_TYPES'].keys())
					print "or create a new one here."
				else:
					print "No mime types yes! Create on here."

				new_task['mime_type'] = prompt("Mime type: ")
			
			if not self.__tr(new_task['mime_type']):
				return False

			if new_task['mime_type'] not in annex_vars['MIME_TYPES'].keys():
				if new_task['short_code'] not in new_task.keys():
					new_task['short_code'] = prompt("Short code for new mime type %s (i.e. \"my_json\"): " \
						% new_task['mime_type'])

				if not self.__tr(new_task['short_code']):
					return False

				annex_vars['MIME_TYPES'].update({ new_task['mime_type'] : new_task['short_code'] })
				annex_vars['MIME_TYPE_MAP'].update({ new_task['short_code'] : new_task['mime_type'] })

			if new_task['mime_type'] not in annex_vars['MIME_TYPE_TASKS'].keys():
				annex_vars['MIME_TYPE_TASKS'][new_task['mime_type']] = []

			annex_vars['MIME_TYPE_TASKS'][new_task['mime_type']].append("%(dir)s.%(name)s.%(name)s" % new_task)

		elif new_task['apply'] == "init":
				if "INITIAL_TASKS" not in annex_vars.keys():
					annex_vars['INITIAL_TASKS'] = []

				annex_vars['INITIAL_TASKS'].append("%(dir)s.%(name)s.%(name)s" % new_task)		

		new_task['dir'] = os.path.join(new_task['root'], new_task['dir'])
		new_task['path'] = os.path.join(new_task['dir'], "%s.py" % new_task['name'])

		with open(os.path.join(self.config['IMAGE_HOME'], "annex", "vars.json"), 'wb+') as M:
			M.write(json.dumps(annex_vars, indent=4))

		routine = [
			"mkdir -p %(dir)s" ,
			"if [ ! -f %(dir)s/__init__.py ]; then touch %(dir)s/__init__.py; fi",
			"sed 's/NAME_OF_TASK/%(name)s/g' $UNVEILLANCE_BUILD_HOME/tmpl/annex.task.py > %(path)s"
		]

		return build_routine([r % new_task for r in routine], dst=self.config['IMAGE_HOME'])

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
		"attach" : annex_project.attach,
		"remove" : annex_project.remove,
		"task" : annex_project.task,
		"asset" : annex_project.asset,
		"validate" : annex_project.validate
	}

	try:
		res = options[argv[1]](argv[3:])
	except Exception as e:
		print e, type(e)

	if type(res) is bool:
		exit(0 if res else -1)
	elif type(res) in [str, unicode]:
		exit(res)

	exit(-1)