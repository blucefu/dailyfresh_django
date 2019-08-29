from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.core.mail import send_mail

from django.contrib.auth import authenticate, login, logout# 导入django自带的用户认证系统,导入login函数

from django.views.generic import View
from django.http import HttpResponse
from django.conf import settings # 从dailyfresh里面settings导入SECRET_KEY 

from user.models import User, Address
from goods.models import GoodsSKU

from celery_tasks.tasks import send_register_active_email # 导入celery发送邮件函数

from itsdangerous import TimedJSONWebSignatureSerializer as Serializer # 导入加密类
from itsdangerous import SignatureExpired

from utils.mixin import LoginRequiredMixin # 先在utils目录下创建LoginRequiredMixin，再导入

# from django.contrib.auth.mixins import PermissionRequiredMixin # django 1.11里面直接导入

from django_redis import get_redis_connection # 导入redis连接函数


import re

# Create your views here.
def register(request):
    '''注册'''
    if request.method == 'GET':
        return render(request, 'register.html')
    else:
        # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        # 数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}{1,2})$', email):
        #     return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        
        # 用户名校验是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user:
             return render(request, 'register.html', {'errmsg': '用户名已经存在'})
        # 进行业务处理：注册
        user = User.objects.create_user(username, password, email)

        # 默认没有激活
        user.is_active = 0
        user.save()
        # 返回应答
        return redirect(reverse('goods:index'))


def register_handle(request):
    '''注册处理'''
    pass
    
# 以后写视图，不要用函数，直接用视图类
# 先导入视图类from django.views.generic import Views
# 然后创建视图类

class RegisterView(View):
    '''注册'''
    def get(self, request):
        '''显示注册'''
        return render(request, 'register.html')
    def post(self, request):
        '''进行注册处理'''
         # 接收数据
        username = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        # 数据校验
        if not all([username, password, email]):
            return render(request, 'register.html', {'errmsg': '数据不完整'})
        # if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}{1,2})$', email):
        #     return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})
        
        # 用户名校验是否重复
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user:
             return render(request, 'register.html', {'errmsg': '用户名已经存在'})
        # 进行业务处理：注册
        user = User.objects.create_user(username, email, password)

        # 默认没有激活
        user.is_active = 0
        user.save()

        # 加密用户身份信息，生成激活token
        serializer = Serializer(settings.SECRET_KEY, 3600) # 创建加密对象
        info = {'confirm': user.id}
        token = serializer.dumps(info)
        token = token.decode() # token是字节码，需要转成字符串

        # 使用celery函数发邮件
        # 1 发出任务，任务放到redis数据库中
        send_register_active_email.delay(email, username, token)

        # 返回应答
        return redirect(reverse('goods:index'))


class ActiveView(View):
    '''用户激活'''
    def get(self, request, token):
        # 定义get方法,同时将urls.py中捕获的token传过来
        # 进行解密
        serializer = Serializer(settings.SECRET_KEY, 3600) # 创建加密对象
        try:
            info = serializer.loads(token)
            # 获取待激活用户id
            user_id = info['confirm']           
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            # 修改用户激活状态并保存
            user.is_active = 1
            user.save()
            #激活后让用户跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活异常处理
            return HttpResponse('激活链接已经过期')
# user/login
class LoginView(View):
    '''用户登录'''
    def get(self, request):
        '''显示登录页面'''
        # 判断是否记住了用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        # 使用模版
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        '''登录校验'''
        # 接收数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不正确'})
        # 业务处理：登录校验  
        user = authenticate(username=username, password=password)
        # 用户名密码正确
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录用户登录状态
                login(request, user)  # login函数是django用户认证系统里面的函数，存储到session 
                
                # 获取登录后要跳转的地址
                # 默认跳转到首页,如果 next 不为空，则跳转到 next
                next_url = request.GET.get('next', reverse('goods:index'))
                # response对象可以设置cookie,所以可以先生成response对象，再通过response对象调用cookie方法，最后再return response
                response = redirect(next_url)

                # 判断是否需要记录用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名,使用cookie
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')

                return response

            else:
                # 用户未激活
                return render(request, 'login.html', {'errmsg': '用户未激活'})
        # 用户名密码错误
        else:
            return render(request, 'login.html', {'errmsg': '用户名密码错误'})
        # 返回应答

# user/logout
class LogoutView(View):
    '''退出登录'''
    def get(self, request):
        '''退出登录'''
        # 清除用户的session信息
        logout(request)
        #页面跳转到首页
        return redirect(reverse('goods:index'))


# /user
class UserInfoView(LoginRequiredMixin, View):
    '''用户中心-信息页'''
    def get(self, request):
        '''显示'''
        # 获取用户信息
        user = request.user
        # 获取用户地址
        address = Address.objects.get_default_address(user)
        # page = 'user'
        # Django使用会话和中间件来拦截request 对象到认证系统中。
        # 它们在每个请求上提供一个request.user属性，表示当前的用户
        # 如果用户未登录 -> request.user属性将设置成 AnonymousUser 的一个实例
        # 如果用户已登录 -> request.user属性将设置成 User 的一个实例
        # 传给user_center_info.html页面一个变量 page = info
        # 可以通过is_authenticated()区分 ，request.user.is_authenticated() 值不为空，表示用户已登录，否则表示用户未登录
        # 

        # 获取用户历史浏览记录
        # 1 链接redis数据库
        conn = get_redis_connection('default')
        # 2 采用 list 方式存储用户历史浏览记录 history_user_id: [goods_id]  
        history_key = 'history_%d' % user.id # 获取key
        sku_id = conn.lrange(history_key, 0, 4) # 获取最新浏览的5个商品id

        # 遍历获取用户浏览商品信息
        goods_li = []
        for id in sku_id:
            goods = GoodsSKU.objects.get(id=id)
            goods_li = append(goods)

        #组织上下文
        context = {'page': 'user',
                    'address': address,
                    'goods_li':goods_li}
 
        return render(request, 'user_center_info.html',context)

# /user/order
class UserOrderView(LoginRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request):
        '''显示'''
        # 获取默认收货地址

        # 传给user_center_order.html页面一个变量 page = order
        return render(request, 'user_center_order.html',  {'page': 'order'})

# /user/address
class AddressView(LoginRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 获取登录用户对应的User对象
        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     address = None # 不存在默认地址

        address = Address.objects.get_default_address(user)
        # 使用模版
        # 传给user_center_site.html页面一个变量 page = address
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        '''添加地址'''
        # 接收数据:收件人、地址、邮编、手机
        recevier = request.POST.get('recevier')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 校验数据
        if not all([recevier, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据格式不正确'})
        if not re.match(r'^1[3|4|5|6|7|8|9][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机格式不正确'})
        # 业务处理:添加地址
        # 很简化的业务：如果用户已经有地址了，添加的地址不作为默认地址
        # 获取登录用户对应的User对象
        user = request.user
        # try:
        # address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        # address = None # 不存在默认地址

        address = Address.objects.get_default_address(user)

        if address:
            is_default = False
        else:
            is_default = True

        # 添加地址
        Address.objects.create(user=user,
                                recevier=recevier,
                                addr=addr,
                                zip_code=zip_code,
                                phone=phone,
                                is_default=is_default)
        # Address.save()
        # 返回应答，刷新页面
        return redirect(reverse('user:address')) # get请求



"""
 
# /user
class UserInfoView(PermissionRequiredMixin, View):
    '''用户中心-信息页'''
    permission_required = 'polls.can_edit'
    def get(self, request):
        '''显示'''
        # 传给user_center_info.html页面一个变量 page = info
        return render(request, 'user_center_info.html', {'page': 'user'})

# /user/order
class UserOrderView(PermissionRequiredMixin, View):
    '''用户中心-订单页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_order.html页面一个变量 page = order
        return render(request, 'user_center_order.html',  {'page': 'order'})

# /user/address
class UserSiteView(PermissionRequiredMixin, View):
    '''用户中心-地址页'''
    def get(self, request):
        '''显示'''
        # 传给user_center_site.html页面一个变量 page = address
        return render(request, 'user_center_site.html', {'page': 'address'})

"""



























