from django.shortcuts import render, redirect
# from django.core.urlresolvers import reverse
from django.views.generic import View # 类视图，而不是函数视图
from django.core.cache import cache # 导入缓存
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django_redis import get_redis_connection # 链接redis数据库
# from order.models import OrderGoods


# Create your views here.
class IndexView(View):
    '''首页类视图'''
    def get(self, request):
        '''显示首页'''
        # 尝试从缓存中获取数据
        context = cache.get('index_page_data')
        if context is None:
            print('测试设置缓存')
            # 获取首页商品种类信息
            types = GoodsType.objects.all()
            # 获取首页banner商品信息
            goods_banners = IndexGoodsBanner.objects.all().order_by('index') # -index从大到小,index从小到大
            # 获取首页频道促销信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by('index')
            # 获取首页商品分类展示信息
            for type in types:
                # 获取type种类首页分类商品的图片展示信息
                image_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=1).order_by('index')
                # 获取type种类首页分类商品的文字展示信息
                title_banners = IndexTypeGoodsBanner.objects.filter(type=type, display_type=0).order_by('index')
                # type_goods_banners = IndexTypeGoodsBanner.objects.all() 不能直接获取图片，
                # 动态给tpye增加属性
                type.image_banners = image_banners
                type.title_banners = title_banners

            context = {'types': types,
                        'goods_banners': goods_banners,
                        'promotion_banners': promotion_banners}

            # 设置缓存
            # cache.set(key,value,timeout)
            cache.set('index_page_data', context, 3600)
            
        # 获取用户购物车商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default') # 链接redis数据库，默认9号库
            cart_key = 'cart_%d' % user.id # 使用hash类型 key field1 value1 field2 value2
            cart_count = conn.hlen(cart_key) # 计算value的个数,注意不是value的和

        # 组织上下文
        context.update(cart_count = cart_count)
                    
        # 使用模版
        return render(request, 'index.html', context) # 然后需要到模版中使用数据

        