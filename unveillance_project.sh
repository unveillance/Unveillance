#! /bin/bash

init_docker_image(){
	IMAGE_HOME=$UNVEILLANCE_BUILD_HOME
	SRC_HOME=$IMAGE_HOME/src
	PROJECT_HOME=$SRC_HOME/unveillance

	mkdir -p $PROJECT_HOME

	cp -R $UNVEILLANCE_BUILD_HOME/.ssh/ $SRC_HOME
	cp $UNVEILLANCE_BUILD_HOME/tmpl/annex.tmpl.json $SRC_HOME/unveillance.secrets.json
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

	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py init
	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

init_annex_project(){
	SRC_HOME=$IMAGE_HOME/annex
	ANNEX_DIR=$IMAGE_HOME/data
	FRONTEND_DIR=$IMAGE_HOME/gui

	cp $UNVEILLANCE_BUILD_HOME/docker.config.json $IMAGE_HOME

	#setup annex
	mkdir -p $SRC_HOME
	mkdir $SRC_HOME/Tasks
	mkdir $SRC_HOME/Models
	mkdir $SRC_HOME/Modules

	cp $UNVEILLANCE_BUILD_HOME/tmpl/project.vars.json $SRC_HOME/vars.json
	
	cd $SRC_HOME
	git init
	git config user.email "unveillance@unveillance.github.io"
	git config user.name "unveillance"
	cp $UNVEILLANCE_BUILD_HOME/tmpl/annex.gitignore .gitignore

	# clone frontend
	mkdir -p $FRONTEND_DIR
	cd $FRONTEND_DIR
	for d in css images js layout; do
		mkdir -p $FRONTEND_DIR/web/$d
	done

	for p in controller_frontend vars conf; do
		cp $UNVEILLANCE_BUILD_HOME/tmpl/frontend.$p.py $p.py
	done
	
	git init
	git submodule add git@github.com:unveillance/UnveillanceInterface.git lib/Frontend
	git submodule update --init --recursive

	touch __init__.py
	touch lib/__init__.py

	pip install -r lib/Frontend/requirements.txt

	# setup frontend
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py build $IMAGE_HOME
	if [ $? -eq 0 ]; then
		cd $FRONTEND_DIR/lib/Frontend
		python setup.py $IMAGE_HOME/unveillance.secrets.json
		run_docker_routine
	else
		do_exit 1
	fi

	# commit project
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py commit $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

update_annex_project(){
	cd $UNVEILLANCE_BUILD_HOME

	python unveillance_project.py validate $IMAGE_HOME
	if ![ $? -eq 0 ]; then
		do_exit 1
	fi

	cd $IMAGE_HOME/annex
	git add .
	git commit -m "annex updated"
	git unveillance push origin master

	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py update $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

attach_annex_project(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py attach $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

start_annex_project(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py start $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
		cd $IMAGE_HOME/gui/lib/Frontend
		./startup.sh $IMAGE_HOME/gui/controller_frontend.py
	else
		do_exit 1
	fi
}

stop_annex_project(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py stop $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
		cd $IMAGE_HOME/gui/lib/Frontend
		./shutdown.sh $IMAGE_HOME/gui/controller_frontend.py
	else
		do_exit 1
	fi
}

remove_annex_project(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py remove $IMAGE_HOME
	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

add_annex_task(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py task $IMAGE_HOME "$@"

	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

add_annex_asset(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py asset $IMAGE_HOME "$@"

	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

add_annex_model(){
	cd $UNVEILLANCE_BUILD_HOME
	python unveillance_project.py model $IMAGE_HOME "$@"

	if [ $? -eq 0 ]; then
		run_docker_routine
	else
		do_exit 1
	fi
}

run_docker_routine(){
	cd $IMAGE_HOME
	if [ -f .routine.sh ]; then
		chmod +x .routine.sh
		cat .routine.sh

		./.routine.sh

		if [ -f .routine.sh ]; then
			rm .routine.sh
		fi

		if [ -f Dockerfile ]; then
			rm Dockerfile
		fi
	fi
}

show_usage(){
	echo "unveillance [init|new|update|start|stop|restart|task]"
}

do_exit(){
	cd $UNVEILLANCE_BUILD_HOME
	deactivate .venv
	echo "_________________________"
	echo ""
	exit $1
}

setup(){
	virtualenv .venv
	source .venv/bin/activate
	pip install -r dutils/requirements.txt
}

echo ""
echo "_________________________"

IMAGE_HOME=$(pwd)

cd $UNVEILLANCE_BUILD_HOME
if [ -d .venv/bin ]; then
	source .venv/bin/activate
else
	setup
fi

ACTION=$1
shift

case "$ACTION" in
	init)
		echo "Initing Unveillance..."
		init_docker_image
		;;
	new)
		echo "New Unveillance Project at $SRC_HOME..."
		init_annex_project
		;;
	update)
		echo "Updating Unveillance Project at $IMAGE_HOME..."
		update_annex_project
		;;
	attach)
		echo "Attaching to Unveillance Project at $IMAGE_HOME"
		attach_annex_project
		;;
	start)
		echo "Starting Unveillance Project at $IMAGE_HOME..."
		start_annex_project
		;;
	stop)
		echo "Stopping Unveillance Project at $IMAGE_HOME..."
		stop_annex_project
		;;
	restart)
		echo "Restarting Unveillance Project at $IMAGE_HOME..."
		stop_annex_project
		sleep 2
		start_annex_project
		;;
	remove)
		echo "Removing Unveillance Project at $IMAGE_HOME..."
		remove_annex_project
		;;
	task)
		echo "Adding Task to Unveillance Project at $IMAGE_HOME..."
		add_annex_task "$@"
		;;
	asset)
		echo "Adding Asset to Unveillance Project at $IMAGE_HOME..."
		add_annex_asset "$@"
		;;
	model)
		echo "Adding Model to Unveillance Project at $IMAGE_HOME..."
		add_annex_model "$@"
		;;
	*)
		echo "Unveillance help"		

		show_usage
		do_exit 1
		;;
esac
do_exit 0



