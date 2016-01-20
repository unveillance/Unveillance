#! /bin/bash

source ~/.bash_profile
ANNEX_DIR=~/unveillance/lib/Annex

show_usage(){
	echo "_________________________"
	echo "$IMAGE_NAME Help"
	echo "_________________________"

	echo "./$IMAGE_NAME.sh [start|stop|restart|reset|update]"
}

stop_annex(){
	echo "_________________________"
	echo "Stopping $IMAGE_NAME"
	echo "_________________________"
	cd $ANNEX_DIR && ./shutdown.sh
}

start_annex(){
	echo "_________________________"
	echo "Starting $IMAGE_NAME"
	echo "_________________________"
	cd $ANNEX_DIR && ./startup.sh
}

restart_annex(){
	echo "_________________________"
	echo "Restarting $IMAGE_NAME"
	echo "_________________________"
	stop_annex
	sleep 2
	start_annex
}

reset_annex(){
	echo "_________________________"
	echo "Resetting $IMAGE_NAME"
	echo "_________________________"
	cd $ANNEX_DIR && ./reset.sh
}

update_annex(){
	echo "_________________________"
	echo "Updating $IMAGE_NAME"
	echo "_________________________"
	cd $ANNEX_DIR && ./update.sh all
}

case "$1" in
	start)
		start_annex
		;;
	stop)
		stop_annex
		;;
	restart)
		restart_annex
		;;
	reset)
		reset_annex
		;;
	update)
		update_annex
		;;
	*)
		show_usage
		exit 1
		;;
esac
exit 0