from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse

from django.http import JsonResponse
from django.db import transaction # 引入数据库事务

from django.views.generic import View


from goods.models import GoodsSKU
from user.models import Address 
from order.models import OrderInfo, OrderGoods

from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from datetime import datetime

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
    '''订单创建'''
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
    '''订单创建'''
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














