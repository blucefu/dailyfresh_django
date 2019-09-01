from django.contrib import admin
from django.core.cache import cache # 导入缓存
from goods.models import GoodsType, GoodsSKU, Goods, GoodsImage, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
# Register your models here.

# admin name:admin password:123456

# user name:smart44 password:11111111

class IndexPromotionBannerAdmin(admin.ModelAdmin):
    '''定义一个类，当IndexPromotionBanner发生修改、删除时，自动更新celery中的静态文件index.html'''
    def save_model(self, request, obj, form, change):
        '''重写ModelAdmin中的save_model方法'''
        super().save_model(request, obj, form, change)

        # 只要save_model方法被调用，就发出任务，让celery重新生成静态首页
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        from celery_tasks.tasks import generate_static_index_html
        generate_static_index_html.delay()

        # 清除首页的缓存数据
        cache.delete('index_page_data')


admin.site.register(GoodsType)

admin.site.register(GoodsSKU, IndexPromotionBannerAdmin)

admin.site.register(Goods, IndexPromotionBannerAdmin)

admin.site.register(GoodsImage, IndexPromotionBannerAdmin)

admin.site.register(IndexGoodsBanner, IndexPromotionBannerAdmin)

admin.site.register(IndexPromotionBanner, IndexPromotionBannerAdmin)

admin.site.register(IndexTypeGoodsBanner, IndexPromotionBannerAdmin)