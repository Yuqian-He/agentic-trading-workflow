from typing import Any, List


class VectorStore:
    def __init__(self, index_path: str):
        self.index_path = index_path
        self.index = None

    def load(self):
        # TODO: 加载 FAISS 或其它向量检索索引
        self.index = []

    def save(self):
        # TODO: 将向量索引保存到磁盘
        pass

    def query(self, query_vector: List[float], top_k: int = 5) -> Any:
        # TODO: 执行向量查询
        return []
