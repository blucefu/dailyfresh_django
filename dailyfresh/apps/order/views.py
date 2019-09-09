from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse

from django.http import JsonResponse
from django.db import transaction # 引入数据库事务
from django.conf import settings

from django.views.generic import View

from goods.models import GoodsSKU
from user.models import Address 
from order.models import OrderInfo, OrderGoods

from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from datetime import datetime

from alipay import AliPay
import os
import time



# from alipay.aop.api.AlipayClientConfig import AlipayClientConfig  # 客户端配置类
# from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient  # 默认客户端类
# from alipay.aop.api.domain.AlipayTradePagePayModel import AlipayTradePagePayModel  # 网站支付数据模型类
# from alipay.aop.api.request.AlipayTradePagePayRequest import AlipayTradePagePayRequest  # 网站支付请求类
# from alipay.aop.api.response.AlipayTradePayResponse import AlipayTradePayResponse

# Create your views here.

# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    '''订单确认页'''
    def post(self, request):    
        # 获取当前用户
        user = request.user

        # 从前端表单中获取sku_ids
        sku_ids = request.POST.getlist('sku_ids') 

        # 校验表单
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        # 链接redis数据库
        conn = get_redis_connection('default')
        # 设置cart_key
        cart_key = 'cart_%d' % user.id

        # 分别保存商品的总件数和总金额
        total_price = 0
        total_count = 0
        skus = [] # 用来保存遍历的sku_id信息
        # 遍历sku_ids，获取用户要购买的商品信息
        for sku_id in sku_ids:
            # 获取商品信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 获取商品数量
            count = conn.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count和amount
            sku.count = count
            sku.amount = amount
            # 将sku保存到skus列表中
            skus.append(sku)
            # 累加商品总件数和总金额
            total_count += int(count)
            total_price += amount

        # 运费在实际开发中有个子系统
        transit_price = 10 # 写死

        # 实际付款
        total_pay = total_price + transit_price

        # 获取用户的地址信息
        addrs = Address.objects.filter(user=user)

        # 订单确认页穿过去的字段中没有sku_id
        # sku_ids是一个列表，需要转成字符串再组织到上下文
        # 组织上下文
        sku_ids = ','.join(sku_ids) # [1,25,35]--> 1,25,35
        context = {'skus': skus, 'total_price': total_price,
                    'total_count': total_count, 
                    'transit_price': transit_price,
                    'total_pay': total_pay, 
                    'addrs': addrs,
                    'sku_ids': sku_ids}
        # 使用模版
        return render(request, 'place_order.html', context)


# /order/commit
# 前端传过来的参数：addr_id pay_method sku_ids
class OrderCommitView1(View):
    '''订单创建-悲观锁'''
    # 装饰post函数，则post里面的所有数据库操作成为一个事务
    @transaction.atomic
    def post(self, request):
        '''订单创建'''
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收前端ajax传过来的参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        # 数据校验
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg':'支付方式非法'})
        try:
            addr = Address.objects.get(id=addr_id)
        except:
            return JsonResponse({'res': 3, 'errmsg':'地址非法'})

        # 业务处理：创建订单
        # 向df_order_info表中添加一条记录，
        # 组织参数：order_id total_count total_price transit_price  
        # order_id:datetime+user_id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # 创建订单记录
            order = OrderInfo.objects.create(order_id=order_id,
                                            user=user,
                                            addr=addr,
                                            pay_method=pay_method,
                                            total_count=total_count,
                                            total_price=total_price,
                                            transit_price=transit_price)
            # 创建订单商品
            # 需要组织的参数:count price
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',') # sku_ids 是一个字符串，需要切割成一个列表
            
            for sku_id in sku_ids:
                try:
                    # 加悲观锁：sql:select * from df_goods_sku where id=sku_id for update;
                    # 别的用户进行到这一步的时候，拿不到锁，就只能等待，事务结束后，锁被解除，其他用户继续执行
                    sku = GoodsSKU.objects.select_for_update().get(id=sku_id)
                except:
                    transaction.savepoint_rollback(save_id) # 事务回滚
                    return JsonResponse({'res': 4, 'errmsg':'商品非法'})
                # 从redis中获取商品数量
                count = conn.hget(cart_key, sku_id)

                # 判断商品库存
                if int(count) > sku.stock:
                    transaction.savepoint_rollback(save_id) # 事务回滚
                    return JsonResponse({'res': 6, 'errmsg':'商品库存不足'})

                OrderGoods.objects.create(order=order,
                                        sku=sku,
                                        count=count,
                                        price=sku.price)
                # 库存减少、销量增加
                sku.stock -= int(count)
                sku.sales += int(count)
                sku.save()
                # 累加计算商品总数和总价格
                amount = sku.price * int(count)
                total_price += amount
                total_count += int(count)

            # 更新订单信息表中商品总数总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

            # 清除购物车中记录
            # sku_ids 是一个列表[1,3,4]，不能直接删除列表，需要加*进行拆包
            conn.hdel(cart_key, *sku_ids)

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'errmsg':'下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)


        # 返回应答
        return JsonResponse({'res':5, 'errmsg':'订单创建成功'})


class OrderCommitView(View):
    '''订单创建-乐观锁'''
    # 装饰post函数，则post里面的所有数据库操作成为一个事务
    @transaction.atomic
    def post(self, request):
        '''订单创建'''
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})
        # 接收前端ajax传过来的参数
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        # 数据校验
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg':'支付方式非法'})
        try:
            addr = Address.objects.get(id=addr_id)
        except:
            return JsonResponse({'res': 3, 'errmsg':'地址非法'})

        # 业务处理：创建订单
        # 向df_order_info表中添加一条记录，
        # 组织参数：order_id total_count total_price transit_price  
        # order_id:datetime+user_id
        order_id = datetime.now().strftime('%Y%m%d%H%M%S')+str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0

        # 设置事务保存点
        save_id = transaction.savepoint()
        try:
            # 创建订单记录
            order = OrderInfo.objects.create(order_id=order_id,
                                            user=user,
                                            addr=addr,
                                            pay_method=pay_method,
                                            total_count=total_count,
                                            total_price=total_price,
                                            transit_price=transit_price)
            # 创建订单商品
            # 需要组织的参数:count price
            conn = get_redis_connection('default')
            cart_key = 'cart_%d' % user.id

            sku_ids = sku_ids.split(',') # sku_ids 是一个字符串，需要切割成一个列表
            
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        # 加悲观锁：sql:select * from df_goods_sku where id=sku_id for update;
                        # 别的用户进行到这一步的时候，拿不到锁，就只能等待，事务结束后，锁被解除，其他用户继续执行
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except:
                        transaction.savepoint_rollback(save_id) # 事务回滚
                        return JsonResponse({'res': 4, 'errmsg':'商品非法'})
                    # 从redis中获取商品数量
                    count = conn.hget(cart_key, sku_id)

                    # 判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id) # 事务回滚
                        return JsonResponse({'res': 6, 'errmsg':'商品库存不足'})

                    # 乐观锁，判断操作前后库存是否一致
                    # 库存减少、销量增加
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)                
                    new_sales = sku.sales + int(count)

                    # 更新数据库数据
                    # sql: update df_goods_sku set stock=new_stock,sales=new_sales
                    # where id=sku_id and stock = orgin_stock = sku.stock
                    res = GoodsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales=new_sales)
                    if res==0:
                        if i == 2: 
                            # 尝试了3次都没有成功
                            transaction.savepoint_rollback(save_id) # 事务回滚
                            return JsonResponse({'res': 8, 'errmsg':'下单失败2'})
                        continue

                    OrderGoods.objects.create(order=order,
                                            sku=sku,
                                            count=count,
                                            price=sku.price)

                    # 累加计算商品总数和总价格
                    amount = sku.price * int(count)
                    total_price += amount
                    total_count += int(count)

                    # 如果就能运行到这里，表示已经更新完，则要跳出循环
                    break

            # 更新订单信息表中商品总数总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()

            # 清除购物车中记录
            # sku_ids 是一个列表[1,3,4]，不能直接删除列表，需要加*进行拆包
            conn.hdel(cart_key, *sku_ids)

        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'errmsg':'下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)


        # 返回应答
        return JsonResponse({'res':5, 'errmsg':'订单创建成功'})


# ajax post 传递参数：order_id
# /order/pay
class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单号为空'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                            user=user,
                                            pay_method=3,
                                            order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单无效'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101100663358", # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'), # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付接口
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        total_pay = order.total_price + order.transit_price # Decimal
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id, # 订单id
            total_amount=str(total_pay), # 支付总金额
            subject='天天生鲜%s'%order_id,
            return_url=None,
            notify_url=None  # 可选, 不填则使用默认notify url
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?' + order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})

 
# ajax post 传递参数：order_id
# /order/check
class CheckPayView(View):
    '''查看订单支付结果'''
    def post(self, request):
        # 用户是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        # 接收参数
        order_id = request.POST.get('order_id')

        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '订单号为空'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                            user=user,
                                            pay_method=3,
                                            order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单无效'})

        # 业务处理:使用python sdk调用支付宝的支付接口
        # 初始化
        alipay = AliPay(
            appid="2016101100663358", # 应用id
            app_notify_url=None,  # 默认回调url
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'), # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )

        # 调用支付宝交易查询接口 response 为一个字典
        while True:
            response = alipay.api_alipay_trade_query(order_id)
            # response ={
                # "trade_no": "2017032121001004070200176844", # 支付宝交易号
                # "code": "10000", # 接口是否调用成功
                # "invoice_amount": "20.00",
                # "open_id": "20880072506750308812798160715407",
                # "fund_bill_list": [
                #   {
                #     "amount": "20.00",
                #     "fund_channel": "ALIPAYACCOUNT"
                #   }
                # ],
                # "buyer_logon_id": "csq***@sandbox.com",
                # "send_pay_date": "2017-03-21 13:29:17",
                # "receipt_amount": "20.00",
                # "out_trade_no": "out_trade_no15",
                # "buyer_pay_amount": "20.00",
                # "buyer_user_id": "2088102169481075",
                # "msg": "Success",
                # "point_amount": "0.00",
                # "trade_status": "TRADE_SUCCESS", # 支付结果：TRADE_SUCCESS支付成功 WAIT_BUYER_PAY等待付款 TRADE_CLOSED超时关闭
                # "total_amount": "20.00"
            # }

            code = response.get('code')
            trade_status = response.get('trade_status')
            if code == '10000' and trade_status == "TRADE_SUCCESS":
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4 # 直接从待支付变成待评价
                order.save() # 对数据库进行修改后，要记得保存
                # 返回应答
                return JsonResponse({'res':3, 'message':'支付成功'})
            elif code == '40004' or(code == '10000' and trade_status == "WAIT_BUYER_PAY"):
                # 等待买家付款
                # 等待几秒再查询 '40004'表示业务目前失败，可能过几秒后成功
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res':4, 'errmsg':'支付失败'})



# /order/comment
class CommentView(LoginRequiredMixin, View):
    '''订单评论'''
    def get(self, request, order_id):
        '''提供评论页面'''
        user = request.user
        # 数据校验
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))
        # 根据订单状态获取订单状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]
        # 获取订单商品信息(为了保存商品小计)
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品小计
            amount = order_sku.price * order_sku.count
            order_sku.amount = amount
        # 动态给order添加order_skus属性
        order.order_skus = order_skus
        #使用模版
        return render(request, 'order_comment.html', {'order':order})

    def post(self, request, order_id):
        '''处理评论内容'''
        user = request.user
        if not order_id:
            return redirect(reverse('user:order'))
        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse('user:order'))
        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        # 获取订单中商品评论内容
        for i in range(1, total_count + 1):
            # 获取评论商品id
            sku_id = request.POST.get('sku_%d' % i) # sku_1 sku_2
            # 获取评论商品内容
            content = request.POST.get('content_%d' % i) # content_1, content_2 
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment =content
            order_goods.save()

        order.order_status = 5
        order.save()

        return redirect(reverse('user:order', kwargs={'page':1}))













