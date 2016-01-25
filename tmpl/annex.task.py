from __future__ import absolute_import

from vars import CELERY_STUB as celery_app

@celery_app.task
def NAME_OF_TASK(uv_task):
	task_tag = "NAME_OF_TASK"

	print "\n\n************** %s [START] ******************\n" % task_tag
	print "NAME_OF_TASK on document %s" % uv_task.doc_id
	uv_task.setStatus(302)


	'''
	Your code here!
	'''


	print "\n\n************** %s [END] ******************\n" % task_tag

	uv_task.finish()
