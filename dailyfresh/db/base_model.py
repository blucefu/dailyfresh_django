from django.db import models


class BaseModel(models.Model):
	# auto_now_add=true 表示当对象被第一次创建时，自动设置当前时间
	# auto_now=true 表示每次保存对象时设置当前时间
	# verbose_name='创建时间' 字段自述名
	create_time = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
	update_time = models.DateTimeField(auto_now=True, verbose_name='更新时间')
	is_delete = models.BooleanField(default=False, verbose_name='删除标记')

	class Meta:
		# 定义抽象类,这样在迁移时候不会被迁移
		abstract = True