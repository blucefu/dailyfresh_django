from django.conf.urls import url
from cart.views import CartAddView, CartInfoView, CartUpadteView, CartDeleteView

urlpatterns = [

    url(r'^$', CartInfoView.as_view(), name='show'), # 购物车页面显示
    url(r'^add$', CartAddView.as_view(), name='add'), # 购物车记录添加 
    url(r'^update$',CartUpadteView.as_view(), name='update'), # 更新购物车
    url(r'^delete$', CartDeleteView.as_view(), name='delete'), # 删除购物车中的商品
 
]
