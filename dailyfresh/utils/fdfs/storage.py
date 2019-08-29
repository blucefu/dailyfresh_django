from django.core.files.storage import Storage # 导入django的储存包
from qiniu import Auth, put_file, etag # 导入七牛云包
import qiniu.config # 导入七牛云配置文件


class FDFSStorage(Storage):
    '''fast dfs文件储存类'''
    def _open(self, name, mode='rb'):
        '''打开文件时使用'''
        pass
    def _save(self, name, content):
        '''保存文件时使用'''
        # name：上传的文件名字
        # content：上传文件内容的File对象，可以实现读取文件内容

        # 创建对象
        # 需要填写的 Access Key 和 Secret Key
        access_key = 'rUo3vBsGl2Lrf-a9MFSb_LYx3QMbZUwuQPmZKfJz'
        secret_key = 'I8mKskRL-69QMhqexXjKYguKK-Ffv-nnhCVCL2PO'
        # 构建鉴权对象
        q = Auth(access_key, secret_key)

        # 要上传的空间
        bucket_name = 'python_study'

        # 上传后保存的文件名
        # key = 'my-python-logo.png'

        # 生成上传 Token，可以指定过期时间等
        token = q.upload_token(bucket_name, name, 3600*24*7)

        # 要上传文件的本地路径
        # localfile = './sync/bbb.jpg'

        # ret, info = put_file(token, key, localfile)

        ret, info = put_file(token, name, content.name)
        '''
        def put_file(up_token, key, file_path, params=None,
             mime_type='application/octet-stream', check_crc=False,
             progress_handler=None, upload_progress_recorder=None, keep_last_modified=False):

        Args:
        up_token:         上传凭证
        key:              上传文件名
        file_path:        上传文件的路径
        params:           自定义变量，规格参考 http://developer.qiniu.com/docs/v6/api/overview/up/response/vars.html#xvar
        mime_type:        上传数据的mimeType
        check_crc:        是否校验crc32
        progress_handler: 上传进度
        upload_progress_recorder: 记录上传进度，用于断点续传

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
        '''

        if ret is None:
            # 上传失败
            raise Exception('上传文件失败')

        # 获取返回的文件ID
        # filename = res.get('Remote file_id') 

        url = 'http://pww211o23.bkt.clouddn.com/{}'.format(key)

        return url

    def exists(self, name):
        '''django判断文件名是否重复'''
        return False

    def url(self, name):
        '''返回访问文件的url路径'''
        return name
