from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse # 反向解析
from django.core.cache import cache # 导入缓存
from django.core.paginator import Paginator  # 导入数据分页
from django.views.generic import View # 类视图，而不是函数视图
from goods.models import GoodsType, GoodsSKU, IndexGoodsBanner, IndexPromotionBanner, IndexTypeGoodsBanner
from django_redis import get_redis_connection # 链接redis数据库
from order.models import OrderGoods # 导入订单中的评论


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

    

# 地址：/goods/goods_id
class DetailView(View):
    '''详情页'''
    def get(self, request, goods_id):
        '''显示详情页,需要捕获goods_id'''
        # 获取商品信息
        try:
            sku = GoodsSKU.objects.get(id=goods_id)
        except GoodsSKU.DoesNotExist:
            # 商品不存在
            return redirect(reverse('goods:index'))
        # 获取首页商品分类信息
        types = GoodsType.objects.all()
        # 获取商品评论信息
        sku_orders = OrderGoods.objects.filter(sku=sku).exclude(comment='') # exclude(comment='')表示排除comment为空的
        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=sku.type).order_by('-create_time')[:2] # 按创建时间倒序排列

        # 获取同一个spu的其他商品信息
        same_spu_skus = GoodsSKU.objects.filter(goods=sku.goods).exclude(id=goods_id)

        # 获取用户购物车商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default') # 链接redis数据库，默认9号库
            cart_key = 'cart_%d' % user.id # 使用hash类型 key field1 value1 field2 value2
            cart_count = conn.hlen(cart_key) # 计算value的个数,注意不是value的和

            # 获取用户历史浏览记录
            conn = get_redis_connection('default')
            history_key = 'history_%d' % user.id # history是list格式
            # 移除列表中的goods_id， 0表示移除全部
            conn.lrem(history_key, 0 ,goods_id)
            # 把goods_id插入到列表的左侧
            conn.lpush(history_key, goods_id)
            # 只保留用户最新浏览的5条信息
            conn.ltrim(history_key, 0, 4)


        # 组织模版上下文
        context = {'sku': sku,
                    'types': types,
                    'sku_orders':  sku_orders,
                    'new_skus': new_skus,
                    'cart_count': cart_count,
                    'same_spu_skus': same_spu_skus}

        return render(request, 'detail.html', context)

# 进入列表页时候需要传的参数：商品种类id、页码、排序方式
# 地址设计：/list/种类id/页码/排序方式
# /list/种类id/页码?sort=排序方式

# /list/种类id/页码?sort=排序方式
class ListView(View):
    '''商品列表页'''
    def get(self, request, type_id, page):
        # 获取商品种类信息
        try:
            type = GoodsType.objects.get(id=type_id)
        except GoodsType.DoesNotExist:
            # 分类不存在
            return redirect(reverse('goods:index'))

        # 获取商品分类全部信息
        types = GoodsType.objects.all()

        # 捕获url中的sort参数
        sort = request.GET.get('sort')
        # sort == default 默认按照商品id排序
        # sort == price 按照商品价格从高到低排序
        # sort == hot 按照商品销量sales从高到低排序

        # 判断sort的值
        if sort == 'price':
            skus = GoodsSKU.objects.filter(type=type).order_by('-price')
        elif sort == 'hot':
            skus = GoodsSKU.objects.filter(type=type).order_by('-sales')
        else:
            sort = 'default'
            skus = GoodsSKU.objects.filter(type=type).order_by('-id')

        # 对商品数据分页
        paginator = Paginator(skus, 1)

        # 获取page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        if page > paginator.num_pages:
            page = 1

        # 获取page页的实例对象，对象里面有商品数据
        skus_page = paginator.page(page)

        # todo: 进行页码控制，页面上最多显示5个页码
        # 1 总页数小于5页，页面上显示所有页码
        # 2 如果当前页是前3页，显示1-5页
        # 3 如果当前页是后3页，显示后5页
        # 4 如果是其他情况，显示当前页前2页，当前页，当前页后2页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages+1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page < 2:
            pages = range(num_pages-2, num_pages+1)
        else:
            pages = range(page-2, page+3)


        # 获取新品信息
        new_skus = GoodsSKU.objects.filter(type=type).order_by('-create_time')[:2] # 按创建时间倒序排列

        # 获取用户购物车商品数目
        user = request.user
        cart_count = 0
        if user.is_authenticated():
            # 用户已登录
            conn = get_redis_connection('default') # 链接redis数据库，默认9号库
            cart_key = 'cart_%d' % user.id # 使用hash类型 key field1 value1 field2 value2
            cart_count = conn.hlen(cart_key) # 计算value的个数,注意不是value的和

        # 组织模版上下文
        context = {'type': type, 'tpyes': types,
                    'skus_page': skus_page,
                    'new_skus': new_skus,
                    'cart_count': cart_count,
                    'sort': sort,
                    'pages': pages}

        return render(request, 'list.html', context)
