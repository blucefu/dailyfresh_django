# 定义索引类
from haystack import indexes
# 导入模型类
from goods.models import GoodsSKU


#指定对于某个类的某些数据建立索引
class GoodsSKUIndex(indexes.SearchIndex, indexes.Indexable):
    '''商品索引类'''
    # 索引字段 use_template=Ture指定根据GoodsSKU表中哪些字段建立索引文件，把说明放在一个文件中
    text = indexes.CharField(document=True, use_template=True)

    def get_model(self):
        return GoodsSKU
        
    # 建立索引的数据
    def index_queryset(self, using=None):
        return self.get_model().objects.all()