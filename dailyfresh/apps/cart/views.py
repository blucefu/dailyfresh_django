from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse # ajax需要用到

from goods.models import GoodsSKU # 需要校验商品id是否存在
from django_redis import get_redis_connection # 获取redis中的商品数据
from utils.mixin import LoginRequiredMixin

# Create your views here.
# 添加商品到购物车：
# 1 请求方式，采用 ajax post
# 如果涉及数据的修改（增删改），采用post
# 如果涉及数据的获取，get
# 2 传递参数：商品ID(sku_id)，商品数量(count)

# /cart/add
class CartAddView(View):
    '''购物车记录添加'''
    def post(self, request):
        # 接收数据
        user = request.user # 获取用户信息
        # 判断用户是否登录
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收ajax传过来的2个数据商品ID和商品数目
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 数据校验1:sku_id 和count不完整
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 数据校验2:count数目出错
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 数据校验3:商品ID出错
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理：添加购物车记录
        # 业务1 获取redis中商品信息
        conn = get_redis_connection('default') # 链接redis数据库
        cart_key = 'cart_%d' % user.id # 设置redis中cart_key的值
        # 尝试获取redis中sku_id的值 -> hget cart_key
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 累加购物车中的商品数目   
            count += int(cart_count)

        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})
        # 如果购物车中没有该商品,则增加
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中商品的条目数
        total_count = conn.hlen(cart_key)

        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '添加成功'})


# /cart
class CartInfoView(LoginRequiredMixin, View):
    '''购物车页面'''
    def get(self, request):
        user = request.user # 获取用户信息
        # 判断用户是否登录
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取用户购物车中的商品信息
        conn = get_redis_connection('default')
        # 获取当前用户在redis中的key
        cart_key = 'cart_%d' % user.id
        # 获取reids中该用户的商品信息{'sku_id':count}
        cart_dict = conn.hgetall(cart_key)

        skus = [] # 用来存储遍历的商品信息
        total_count = 0
        total_price = 0
        # 遍历 cart_dict
        for sku_id, count in cart_dict.items():
            # 根据商品ID获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品小计
            amount = sku.price * int(count)
            # 动态给sku对象新增一个属性amount，用来保存商品的小机
            sku.amount = amount
            # 动态给sku对象新增一个属性count，用来保存商品的数目
            sku.count = count
            # 将sku添加到 skus列表中
            skus.append(sku)

            total_count += int(count)
            total_price += amount
        # 组织上下文
        context = {'total_count': total_count, 
                    'total_price': total_price,
                    'skus': skus}

        return render(request, 'cart.html', context)



# 更新购物车页面中商品数量 ajagx post
# /cart/update
class CartUpadteView(View):
    '''更新购物车页面中商品数量'''
    def post(self, request):
        # 获取当前用户
        user = request.user 
        # 判断用户是否登录
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取数据:接收ajax传过来的2个数据商品ID和商品数目
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')

        # 校验数据
        # 数据校验1:sku_id 和count不完整
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 数据校验2:count数目出错
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 数据校验3:商品ID出错
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})

        # 业务处理:更新购物车中商品数据
        conn = get_redis_connection('default') # 链接redis数据库
        cart_key = 'cart_%d' % user.id

        # 校验商品库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '库存不足'})

        # 更新商品数量
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中商品的总件数 {'1':5, '2': 4}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'message': '更新成功'})


# 删除购物车商品
# ajax post 请求，传递参数:商品ID (sku_id)
# /cart/delete
class CartDeleteView(View):
    def post(self, request):
        # 获取当前用户
        user = request.user 
        # 判断用户是否登录
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 获取数据:接收ajax传过来的商品ID sku_id
        sku_id = request.POST.get('sku_id')

        # 校验参数,sku_id是否为空
        if not sku_id:
            return JsonResponse({'res': 1, 'errmsg': '商品ID无效'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '商品不存在'})

        # 业务处理
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 删除
        conn.hdel(cart_key, sku_id)

        # 计算用户购物车中商品的总件数 {'1':5, '2': 4}
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)


        # 返回应答
        return JsonResponse({'res': 3, 'total_count': total_count, 'message': '删除成功'})

