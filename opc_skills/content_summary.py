"""
OPC-Agents 内容摘要技能

功能：
- 文本摘要（提取式/抽象式）
- 大纲生成
- 关键词提取
- 关键信息抽取
"""

import re
from typing import Dict, List, Optional, Tuple
from collections import Counter


class ContentSummarySkill:
    """内容摘要技能"""
    
    # 技能元数据
    METADATA = {
        'name': 'content_summary',
        'version': '1.0.0',
        'description': '智能内容摘要技能，支持文本摘要/大纲生成/关键词提取',
        'author': 'OPC-Agents Team',
        'category': 'content_processing',
        'tags': ['摘要', '大纲', '关键词', '内容处理'],
        'permissions': [],
    }
    
    # 中文停用词（简化版）
    STOP_WORDS = set([
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
        '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
        '你', '会', '着', '没有', '看', '好', '自己', '这', '那',
        '他', '她', '它', '们', '这个', '那个', '什么', '怎么', '可以',
        '没', '把', '让', '向', '从', '为', '对', '给', '过', '后',
        '而', '及', '与', '或', '但', '如果', '因为', '所以', '虽然',
        '但是', '而且', '或者', '如果', '即使', '尽管', '不管', '无论',
        '已经', '正在', '将要', '应该', '能够', '可能', '必须', '需要',
    ])
    
    # 大纲标记词
    OUTLINE_MARKERS = {
        'first': ['首先', '第一', '其一', '一方面'],
        'second': ['其次', '第二', '其二', '另一方面'],
        'third': ['再次', '第三', '其三', '此外'],
        'finally': ['最后', '最终', '总之', '综上所述', '总而言之'],
        'emphasis': ['重要的是', '值得注意的是', '特别是', '尤其'],
        'example': ['例如', '比如', '举例来说', '以...为例'],
        'cause': ['因为', '由于', '原因是'],
        'effect': ['所以', '因此', '因而', '导致', '结果是'],
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化内容摘要技能
        
        Args:
            config: 配置字典
        """
        self.config = config or {}
        self.default_summary_ratio = self.config.get('summary_ratio', 0.3)
        self.default_keywords_count = self.config.get('keywords_count', 5)
    
    def execute(self, 
                operation: str,
                text: str,
                **kwargs) -> Dict:
        """
        执行内容摘要操作
        
        Args:
            operation: 操作类型 ('summarize', 'outline', 'keywords', 'extract')
            text: 输入文本
            **kwargs: 其他参数
            
        Returns:
            Dict: 操作结果
        """
        try:
            if operation == 'summarize':
                return self._summarize(text, **kwargs)
            elif operation == 'outline':
                return self._generate_outline(text, **kwargs)
            elif operation == 'keywords':
                return self._extract_keywords(text, **kwargs)
            elif operation == 'extract':
                return self._extract_key_info(text, **kwargs)
            else:
                return {
                    'success': False,
                    'error': f'不支持的操作：{operation}',
                    'supported_operations': ['summarize', 'outline', 'keywords', 'extract']
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
            }
    
    def _summarize(self, 
                   text: str,
                   ratio: Optional[float] = None,
                   max_sentences: Optional[int] = None,
                   method: str = 'extractive',
                   **kwargs) -> Dict:
        """
        生成文本摘要
        
        Args:
            text: 输入文本
            ratio: 摘要比例（0-1），默认 0.3
            max_sentences: 最大句子数
            method: 方法（'extractive' 提取式 / 'abstractive' 抽象式）
            
        Returns:
            Dict: {
                'success': bool,
                'summary': str,
                'original_length': int,
                'summary_length': int,
                'compression_ratio': float
            }
        """
        # 分割句子
        sentences = self._split_sentences(text)
        
        if len(sentences) <= 1:
            return {
                'success': True,
                'summary': text,
                'original_length': len(text),
                'summary_length': len(text),
                'compression_ratio': 1.0,
                'method': method,
            }
        
        # 计算重要度
        sentence_scores = self._score_sentences(sentences)
        
        # 排序并选择 top 句子
        ratio = ratio or self.default_summary_ratio
        top_n = max_sentences or int(len(sentences) * ratio)
        top_n = max(1, min(top_n, len(sentences)))
        
        # 获取最重要的句子
        ranked_sentences = sorted(
            enumerate(sentence_scores),
            key=lambda x: x[1],
            reverse=True
        )[:top_n]
        
        # 按原文顺序重组
        ranked_sentences.sort(key=lambda x: x[0])
        summary_sentences = [sentences[i] for i, _ in ranked_sentences]
        
        summary = ' '.join(summary_sentences)
        
        return {
            'success': True,
            'summary': summary,
            'original_length': len(text),
            'summary_length': len(summary),
            'compression_ratio': len(summary) / len(text) if text else 0,
            'method': method,
            'sentences_count': len(summary_sentences),
        }
    
    def _generate_outline(self, 
                          text: str,
                          include_examples: bool = True,
                          **kwargs) -> Dict:
        """
        生成文本大纲
        
        Args:
            text: 输入文本
            include_examples: 是否包含示例
            
        Returns:
            Dict: {
                'success': bool,
                'outline': str,
                'structure': List[Dict],
                'main_points': List[str]
            }
        """
        sentences = self._split_sentences(text)
        
        # 识别结构性句子
        structure = []
        main_points = []
        
        for i, sentence in enumerate(sentences):
            # 检测大纲标记词
            marker_type = self._detect_outline_marker(sentence)
            
            if marker_type:
                structure.append({
                    'index': i,
                    'type': marker_type,
                    'sentence': sentence,
                })
                main_points.append(sentence)
            elif i == 0:  # 第一句通常是主题句
                structure.append({
                    'index': i,
                    'type': 'introduction',
                    'sentence': sentence,
                })
                main_points.append(sentence)
            elif i == len(sentences) - 1:  # 最后一句通常是总结
                structure.append({
                    'index': i,
                    'type': 'conclusion',
                    'sentence': sentence,
                })
                main_points.append(sentence)
        
        # 生成大纲文本
        outline_lines = []
        for item in structure:
            prefix = self._get_marker_prefix(item['type'])
            outline_lines.append(f"{prefix} {item['sentence']}")
        
        outline = '\n'.join(outline_lines)
        
        return {
            'success': True,
            'outline': outline,
            'structure': structure,
            'main_points': main_points,
            'points_count': len(main_points),
        }
    
    def _extract_keywords(self, 
                          text: str,
                          top_k: Optional[int] = None,
                          min_length: int = 2,
                          **kwargs) -> Dict:
        """
        提取关键词
        
        Args:
            text: 输入文本
            top_k: 返回的关键词数量
            min_length: 最小词长
            
        Returns:
            Dict: {
                'success': bool,
                'keywords': List[str],
                'scores': Dict[str, float]
            }
        """
        top_k = top_k or self.default_keywords_count
        
        # 分词（简单实现，基于字符和常用词）
        words = self._tokenize_chinese(text)
        
        # 过滤停用词和短词
        filtered_words = [
            word for word in words
            if len(word) >= min_length
            and word not in self.STOP_WORDS
            and not self._is_punctuation(word)
        ]
        
        # 统计词频
        word_freq = Counter(filtered_words)
        
        # 获取 top-k 关键词
        top_keywords = word_freq.most_common(top_k)
        
        keywords = [word for word, _ in top_keywords]
        scores = {word: freq / len(filtered_words) if filtered_words else 0 
                  for word, freq in top_keywords}
        
        return {
            'success': True,
            'keywords': keywords,
            'scores': scores,
            'total_words': len(filtered_words),
            'unique_words': len(word_freq),
        }
    
    def _extract_key_info(self, 
                          text: str,
                          info_types: Optional[List[str]] = None,
                          **kwargs) -> Dict:
        """
        提取关键信息
        
        Args:
            text: 输入文本
            info_types: 信息类型 ['dates', 'numbers', 'names', 'organizations']
            
        Returns:
            Dict: {
                'success': bool,
                'dates': List[str],
                'numbers': List[str],
                'names': List[str],
                'organizations': List[str],
                'key_sentences': List[str]
            }
        """
        info_types = info_types or ['dates', 'numbers', 'names', 'organizations']
        
        result = {
            'success': True,
        }
        
        # 提取日期
        if 'dates' in info_types:
            dates = self._extract_dates(text)
            result['dates'] = dates
        
        # 提取数字
        if 'numbers' in info_types:
            numbers = self._extract_numbers(text)
            result['numbers'] = numbers
        
        # 提取人名（简单实现）
        if 'names' in info_types:
            names = self._extract_names(text)
            result['names'] = names
        
        # 提取组织（简单实现）
        if 'organizations' in info_types:
            orgs = self._extract_organizations(text)
            result['organizations'] = orgs
        
        # 提取关键句子
        sentences = self._split_sentences(text)
        sentence_scores = self._score_sentences(sentences)
        
        # 获取 top 3 关键句
        top_indices = sorted(
            range(len(sentence_scores)),
            key=lambda i: sentence_scores[i],
            reverse=True
        )[:3]
        
        result['key_sentences'] = [sentences[i] for i in top_indices]
        
        return result
    
    # ========== 辅助方法 ==========
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割句子"""
        # 中文句子分割
        sentences = re.split(r'[。！？!?；;]', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _tokenize_chinese(self, text: str) -> List[str]:
        """
        中文分词（简化版）
        
        实际应用中应该使用 jieba 等专业分词库
        """
        # 简单实现：按 2-4 字组词
        words = []
        for i in range(len(text) - 1):
            for j in range(i + 2, min(i + 5, len(text))):
                word = text[i:j]
                if self._is_valid_word(word):
                    words.append(word)
        return words
    
    def _is_valid_word(self, word: str) -> bool:
        """判断是否是有效词（简化版）"""
        # 只包含中文字符
        return all('\u4e00' <= c <= '\u9fff' for c in word)
    
    def _is_punctuation(self, text: str) -> bool:
        """判断是否是标点"""
        return all(c in '，。！？；：""''、·（）《》【】…—' for c in text)
    
    def _score_sentences(self, sentences: List[str]) -> List[float]:
        """
        句子重要度评分
        
        基于：
        1. 句子位置（开头结尾更重要）
        2. 包含关键词的频率
        3. 句子长度（适中更好）
        """
        scores = []
        total_sentences = len(sentences)
        
        # 计算词频
        word_freq = Counter()
        for sentence in sentences:
            words = self._tokenize_chinese(sentence)
            filtered = [w for w in words if w not in self.STOP_WORDS]
            word_freq.update(filtered)
        
        for i, sentence in enumerate(sentences):
            score = 0.0
            
            # 位置分数（开头结尾更重要）
            if i == 0:
                score += 3.0
            elif i == total_sentences - 1:
                score += 2.0
            elif i < total_sentences * 0.2:
                score += 1.5
            elif i > total_sentences * 0.8:
                score += 1.0
            
            # 关键词分数
            words = self._tokenize_chinese(sentence)
            for word in words:
                if word in word_freq:
                    score += word_freq[word] * 0.1
            
            # 长度分数（适中更好）
            length = len(sentence)
            if 20 <= length <= 100:
                score += 1.0
            elif length > 100:
                score += 0.5
            
            scores.append(score)
        
        return scores
    
    def _detect_outline_marker(self, sentence: str) -> Optional[str]:
        """检测大纲标记词"""
        for marker_type, markers in self.OUTLINE_MARKERS.items():
            for marker in markers:
                if marker in sentence:
                    return marker_type
        return None
    
    def _get_marker_prefix(self, marker_type: str) -> str:
        """获取大纲标记前缀"""
        prefixes = {
            'introduction': '【引言】',
            'first': '【第一】',
            'second': '【第二】',
            'third': '【第三】',
            'finally': '【总结】',
            'emphasis': '【重点】',
            'example': '【示例】',
            'cause': '【原因】',
            'effect': '【结果】',
            'conclusion': '【结论】',
        }
        return prefixes.get(marker_type, '【要点】')
    
    def _extract_dates(self, text: str) -> List[str]:
        """提取日期"""
        patterns = [
            r'\d{4}年\d{1,2}月\d{1,2}日',
            r'\d{4}-\d{1,2}-\d{1,2}',
            r'\d{4}/\d{1,2}/\d{1,2}',
            r'\d{1,2}月\d{1,2}日',
            r'今天|明天|后天|昨天|前天',
            r'本周|下周|上月|明年',
        ]
        
        dates = []
        for pattern in patterns:
            dates.extend(re.findall(pattern, text))
        return list(set(dates))
    
    def _extract_numbers(self, text: str) -> List[str]:
        """提取数字"""
        patterns = [
            r'\d+\.?\d*\s*(%|亿元|万元|亿|万|千|百)',
            r'\d+\.?\d*',
            r'百分之\d+\.?\d*',
        ]
        
        numbers = []
        for pattern in patterns:
            numbers.extend(re.findall(pattern, text))
        return list(set(numbers))
    
    def _extract_names(self, text: str) -> List[str]:
        """提取人名（简化版）"""
        # 简单匹配：姓氏 + 名字（2-3 字）
        pattern = r'[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卡齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储晋汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公]'
        names = re.findall(pattern, text)
        return list(set(names))[:10]  # 限制数量
    
    def _extract_organizations(self, text: str) -> List[str]:
        """提取组织机构（简化版）"""
        patterns = [
            r'[^\s]+公司',
            r'[^\s]+集团',
            r'[^\s]+有限公司',
            r'[^\s]+大学',
            r'[^\s]+学院',
            r'[^\s]+研究所',
            r'[^\s]+部门',
            r'[^\s]+委员会',
        ]
        
        orgs = []
        for pattern in patterns:
            orgs.extend(re.findall(pattern, text))
        return list(set(orgs))[:10]  # 限制数量
    
    def get_schema(self) -> Dict:
        """返回输入输出 schema"""
        return {
            'input': {
                'operation': {
                    'type': 'string',
                    'required': True,
                    'description': '操作类型',
                    'enum': ['summarize', 'outline', 'keywords', 'extract']
                },
                'text': {
                    'type': 'string',
                    'required': True,
                    'description': '输入文本'
                },
                'ratio': {
                    'type': 'float',
                    'required': False,
                    'description': '摘要比例（0-1）'
                },
                'top_k': {
                    'type': 'integer',
                    'required': False,
                    'description': '关键词数量'
                },
            },
            'output': {
                'success': {'type': 'boolean'},
                'summary': {'type': 'string'},
                'outline': {'type': 'string'},
                'keywords': {'type': 'array'},
                'error': {'type': 'string'},
            }
        }


# 便捷函数
def summarize(text: str, **kwargs) -> Dict:
    """生成文本摘要"""
    skill = ContentSummarySkill()
    return skill.execute('summarize', text, **kwargs)


def generate_outline(text: str, **kwargs) -> Dict:
    """生成大纲"""
    skill = ContentSummarySkill()
    return skill.execute('outline', text, **kwargs)


def extract_keywords(text: str, **kwargs) -> Dict:
    """提取关键词"""
    skill = ContentSummarySkill()
    return skill.execute('keywords', text, **kwargs)


def extract_key_info(text: str, **kwargs) -> Dict:
    """提取关键信息"""
    skill = ContentSummarySkill()
    return skill.execute('extract', text, **kwargs)


# 测试
if __name__ == '__main__':
    print("=" * 60)
    print("内容摘要技能测试")
    print("=" * 60)
    
    # 测试文本
    test_text = """
    人工智能（AI）是 21 世纪最重要的技术革命之一。首先，人工智能在医疗领域的应用已经取得了显著成果，例如 AI 辅助诊断系统可以准确识别癌症早期症状。其次，在交通领域，自动驾驶技术正在快速发展，特斯拉、百度等公司都已经推出了自动驾驶汽车。第三，人工智能在金融领域的应用也非常广泛，包括智能投顾、风险控制等。此外，AI 还在教育、零售、制造等行业发挥着重要作用。

    值得注意的是，人工智能的发展也带来了一些挑战。比如数据隐私问题、就业替代问题、算法偏见等。因此，我们需要在推动 AI 技术发展的同时，也要关注其可能带来的社会影响。

    总之，人工智能正在深刻改变我们的生活和工作方式。未来，随着技术的不断进步，AI 将会更加普及和智能化。
    """
    
    skill = ContentSummarySkill()
    
    # 测试 1: 文本摘要
    print("\n1. 测试文本摘要")
    result = skill.execute('summarize', test_text, ratio=0.3)
    
    if result['success']:
        print(f"✅ 摘要生成成功")
        print(f"原文长度：{result['original_length']} 字")
        print(f"摘要长度：{result['summary_length']} 字")
        print(f"压缩率：{result['compression_ratio']:.2f}")
        print(f"\n摘要内容：\n{result['summary']}")
    else:
        print(f"❌ 摘要生成失败：{result.get('error', '未知错误')}")
    
    # 测试 2: 大纲生成
    print("\n" + "=" * 60)
    print("2. 测试大纲生成")
    result = skill.execute('outline', test_text)
    
    if result['success']:
        print(f"✅ 大纲生成成功")
        print(f"主要观点数：{result['points_count']}")
        print(f"\n大纲内容：\n{result['outline']}")
    else:
        print(f"❌ 大纲生成失败：{result.get('error', '未知错误')}")
    
    # 测试 3: 关键词提取
    print("\n" + "=" * 60)
    print("3. 测试关键词提取")
    result = skill.execute('keywords', test_text, top_k=10)
    
    if result['success']:
        print(f"✅ 关键词提取成功")
        print(f"总词数：{result['total_words']}")
        print(f"独特词数：{result['unique_words']}")
        print(f"\nTop 10 关键词：")
        for i, keyword in enumerate(result['keywords'][:10], 1):
            score = result['scores'].get(keyword, 0)
            print(f"  {i}. {keyword} (频率：{score:.3f})")
    else:
        print(f"❌ 关键词提取失败：{result.get('error', '未知错误')}")
    
    # 测试 4: 关键信息提取
    print("\n" + "=" * 60)
    print("4. 测试关键信息提取")
    result = skill.execute('extract', test_text)
    
    if result['success']:
        print(f"✅ 关键信息提取成功")
        print(f"日期：{result.get('dates', [])}")
        print(f"数字：{result.get('numbers', [])}")
        print(f"组织：{result.get('organizations', [])}")
        print(f"\n关键句子：")
        for i, sentence in enumerate(result['key_sentences'], 1):
            print(f"  {i}. {sentence}")
    else:
        print(f"❌ 关键信息提取失败：{result.get('error', '未知错误')}")
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
