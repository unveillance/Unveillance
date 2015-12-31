#! /bin/bash

UNVEILLANCE_BUILD_HOME=$(cd "$(dirname "{BASH_SOURCE[0]}")" && pwd)
if [[ $2 ]]; then
	IMAGE_HOME=$2
	
else
	IMAGE_HOME=$UNVEILLANCE_BUILD_HOME
fi

SRC_HOME=$IMAGE_HOME/src

run_docker_routine(){
	cd $IMAGE_HOME
	chmod +x .routine.sh
	./.routine.sh
	rm .routine.sh
}

init_docker_image(){
	PROJECT_HOME=$SRC_HOME/Unveillance
	mkdir -p $PROJECT_HOME

	cp -R $UNVEILLANCE_BUILD_HOME/.ssh/ $SRC_HOME
	for tmpl in install.sh run.sh; do
		cp $UNVEILLANCE_BUILD_HOME/tmpl/project.$tmpl $SRC_HOME/$tmpl
	done

	cd $PROJECT_HOME
	git init
	touch __init__.py
	git submodule add git@github.com:/Unveillance/UnveillanceAnnex lib/Annex

	cp $UNVEILLANCE_BUILD_HOME/tmpl/project.gitignore $PROJECT_HOME/.gitignore
	for tmpl in setup.sh unveillance.sh vars.json; do
		cp $UNVEILLANCE_BUILD_HOME/tmpl/project.$tmpl $PROJECT_HOME/$tmpl
	done
}

show_usage(){
	echo "unveillance [init|new|update]"
}

do_exit(){
	deactivate venv
	exit $1
}

setup(){
	virtualenv venv
	source venv/bin/activate
	pip install -r dutils/requirements.txt
}

ls venv
if [ $? -eq 1 ]; then
	setup
else
	source venv/bin/activate
fi

case "$1" in
	init)
		echo "_________________________"
		echo "Initing Unveillance..."
		echo "_________________________"

		init_docker_image
		cd $UNVEILLANCE_BUILD_HOME
		python unveillance_project.py init
		if [ $? -eq 0 ]; then
			#run_docker_routine
			echo "would run docker routine"
			cat .routine.sh
		fi
		;;
	new)
		echo "_________________________"
		echo "New Unveillance Project..."
		echo "_________________________"
		;;
	*)
		echo "_________________________"
		echo "Unveillance help"
		echo "_________________________"

		show_usage
		do_exit 1
		;;
esac
do_exit 0



