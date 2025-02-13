import platform
import logging
import json
import os
import time
from typing import Dict, Any, Optional, List
from datetime import datetime
import cpuinfo
import psutil
import GPUtil
import requests

# Configuração básica de logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class ProcessorInfoCollector:
    """Coletor de informações do processador com tratamento de erros aprimorado"""
    
    def __init__(self):
        self._raw_cpu_info = cpuinfo.get_cpu_info()
        self._flags = self._raw_cpu_info.get('flags', [])
        self._logger = logging.getLogger(__name__)
        
    @property
    def _timestamp(self) -> str:
        """Retorna timestamp no formato ISO"""
        return datetime.now().isoformat()

    def _get_architecture_details(self) -> Dict[str, Any]:
        """Coleta detalhes da arquitetura do processador"""
        return {
            'bits': self._raw_cpu_info.get('bits', 'N/A'),
            'arch': self._raw_cpu_info.get('arch_string_raw', 'N/A'),
            'family': self._raw_cpu_info.get('family', 'N/A'),
            'model': self._raw_cpu_info.get('model', 'N/A'),
            'stepping': self._raw_cpu_info.get('stepping', 'N/A')
        }

    def _get_virtualization_details(self) -> Dict[str, Any]:
        """Detalhes avançados de virtualização com tratamento de erros"""
        return {
            'supported': any(x in self._flags for x in ['vmx', 'svm']),
            'type': 'Intel VT-x' if 'vmx' in self._flags else 'AMD-V' if 'svm' in self._flags else 'N/A',
            'enabled': self._check_virtualization_enabled()
        }

    def _check_virtualization_enabled(self) -> Optional[bool]:
        """Verifica se a virtualização está habilitada com fallback seguro"""
        try:
            if platform.system() == 'Windows':
                import winreg
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_LOCAL_MACHINE,
                        r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Virtualization'
                    ) as key:
                        return winreg.QueryValueEx(key, 'Enabled')[0] == 1
                except FileNotFoundError:
                    self._logger.warning("Chave de registro de virtualização não encontrada")
                    return None
            elif platform.system() == 'Linux':
                with open('/proc/cpuinfo', 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                    return 'svm' in content or 'vmx' in content
            return None
        except Exception as e:
            self._logger.error(f"Falha na verificação de virtualização: {str(e)}")
            return None

    def _get_cache_details(self) -> Dict[str, Any]:
        """Coleta detalhes hierárquicos do cache com fallbacks"""
        return {
            'l1': {
                'instruction': self._raw_cpu_info.get('l1_instruction_cache_size', 'N/A'),
                'data': self._raw_cpu_info.get('l1_data_cache_size', 'N/A')
            },
            'l2': self._raw_cpu_info.get('l2_cache_size', 'N/A'),
            'l3': self._raw_cpu_info.get('l3_cache_size', 'N/A'),
            'associativity': {
                'l1': self._raw_cpu_info.get('l1_cache_associativity', 'N/A'),
                'l2': self._raw_cpu_info.get('l2_cache_associativity', 'N/A')
            }
        }

    def _get_extension_support(self) -> Dict[str, bool]:
        """Mapeamento completo de extensões suportadas"""
        extensions = [
            'sse', 'sse2', 'sse3', 'ssse3', 'sse4_1', 'sse4_2',
            'avx', 'avx2', 'avx512f', 'aes', 'fma3', 'f16c',
            'sha', 'tsc', 'tsx', 'rdrand', 'rdseed', 'mmx'
        ]
        return {ext: ext in self._flags for ext in extensions}

    def _get_performance_metrics(self) -> Dict[str, Any]:
        """Métricas de desempenho em tempo real com tratamento robusto"""
        try:
            freq = psutil.cpu_freq()
            loads = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else (None, None, None)
            
            return {
                'frequency': {
                    'current': freq.current if freq else None,
                    'max': self._raw_cpu_info.get('hz_advertised_friendly', 'N/A')
                },
                'load_average': {
                    '1min': loads[0],
                    '5min': loads[1],
                    '15min': loads[2]
                },
                'usage_percent': psutil.cpu_percent(percpu=True),
                'temperature': self._get_cpu_temperature()
            }
        except Exception as e:
            self._logger.error(f"Erro nas métricas de desempenho: {str(e)}")
            return {}

    def _get_cpu_temperature(self) -> Optional[float]:
        """Tenta obter a temperatura do CPU de forma segura"""
        try:
            if platform.system() == 'Windows':
                try:
                    import wmi
                    w = wmi.WMI(namespace=r'root\wmi')
                    temps = w.MSAcpi_ThermalZoneTemperature()
                    if temps:
                        return round(temps[0].CurrentTemperature / 10 - 273.15, 1)
                    return None
                except ImportError:
                    self._logger.warning("Módulo WMI não instalado. Use: pip install wmi")
                    return None
            elif platform.system() == 'Linux':
                # Verifica múltiplas zonas térmicas
                for zone in range(5):
                    path = f'/sys/class/thermal/thermal_zone{zone}/temp'
                    if os.path.exists(path):
                        with open(path, 'r', encoding='utf-8') as f:
                            return round(float(f.read().strip()) / 1000, 1)
                return None
            return None
        except Exception as e:
            self._logger.error(f"Falha na leitura de temperatura: {str(e)}")
            return None

    def to_json(self) -> Dict[str, Any]:
        """Retorna todos os dados coletados em formato estruturado"""
        try:
            return {
                'metadata': {
                    'timestamp': self._timestamp,
                    'platform': platform.platform(),
                    'python_version': platform.python_version(),
                    'script_version': '2.1.0'
                },
                'identification': {
                    'vendor': self._raw_cpu_info.get('vendor_id_raw', 'N/A'),
                    'brand': self._raw_cpu_info.get('brand_raw', 'N/A'),
                    'is_intel': 'GenuineIntel' in self._raw_cpu_info.get('vendor_id_raw', ''),
                    'is_amd': 'AuthenticAMD' in self._raw_cpu_info.get('vendor_id_raw', '')
                },
                'architecture': self._get_architecture_details(),
                'cores': {
                    'physical': psutil.cpu_count(logical=False),
                    'logical': psutil.cpu_count(),
                    'hyperthreading': psutil.cpu_count() > psutil.cpu_count(logical=False)
                },
                'cache': self._get_cache_details(),
                'virtualization': self._get_virtualization_details(),
                'extensions': self._get_extension_support(),
                'performance': self._get_performance_metrics(),
                'raw_flags': self._flags
            }
        except Exception as e:
            self._logger.critical(f"Falha crítica na coleta de dados: {str(e)}")
            return {'error': 'Falha na coleta de informações do processador'}

def benchmark(repetitions: int = 5) -> Dict[str, Any]:
    """
    Executa o benchmark várias vezes e retorna a média dos resultados.
    :param repetitions: Número de repetições para calcular a média.
    :return: Dicionário com os resultados do benchmark.
    """
    results = {
        'execution_time_ms': [],
        'memory_usage_mb': [],
        'cpu_usage_percent': [],
        'gpu_usage_percent': [],
        'gpu_temperature': [],
        'gpu_memory_usage_mb': [],
        'process_memory_usage_mb': []
    }

    for _ in range(repetitions):
        start_time = time.time()
        start_memory = psutil.virtual_memory().used
        start_cpu = psutil.cpu_percent()
        gpus = GPUtil.getGPUs()
        start_gpu = gpus[0].load * 100 if gpus else None
        start_gpu_memory = gpus[0].memoryUsed if gpus else None
        start_gpu_temp = gpus[0].temperature if gpus else None

        # Coleta de informações do processador
        collector = ProcessorInfoCollector()
        result = collector.to_json()

        end_time = time.time()
        end_memory = psutil.virtual_memory().used
        end_cpu = psutil.cpu_percent()
        end_gpu = gpus[0].load * 100 if gpus else None
        end_gpu_memory = gpus[0].memoryUsed if gpus else None
        end_gpu_temp = gpus[0].temperature if gpus else None

        # Cálculo das métricas
        results['execution_time_ms'].append((end_time - start_time) * 1000)
        results['memory_usage_mb'].append((end_memory - start_memory) / (1024 * 1024))
        results['cpu_usage_percent'].append(end_cpu - start_cpu)
        results['gpu_usage_percent'].append(end_gpu - start_gpu if end_gpu and start_gpu else None)
        results['gpu_temperature'].append(end_gpu_temp if end_gpu_temp else None)
        results['gpu_memory_usage_mb'].append(end_gpu_memory - start_gpu_memory if end_gpu_memory and start_gpu_memory else None)
        results['process_memory_usage_mb'].append(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024))

        # Intervalo entre execuções para evitar sobrecarga
        time.sleep(1)

    # Calcula a média dos resultados
    avg_results = {
        'execution_time_ms': sum(results['execution_time_ms']) / repetitions,
        'memory_usage_mb': sum(results['memory_usage_mb']) / repetitions,
        'cpu_usage_percent': sum(results['cpu_usage_percent']) / repetitions,
        'gpu_usage_percent': sum([x for x in results['gpu_usage_percent'] if x is not None]) / repetitions if any(x is not None for x in results['gpu_usage_percent']) else None,
        'gpu_temperature': sum([x for x in results['gpu_temperature'] if x is not None]) / repetitions if any(x is not None for x in results['gpu_temperature']) else None,
        'gpu_memory_usage_mb': sum([x for x in results['gpu_memory_usage_mb'] if x is not None]) / repetitions if any(x is not None for x in results['gpu_memory_usage_mb']) else None,
        'process_memory_usage_mb': sum(results['process_memory_usage_mb']) / repetitions
    }

    return result, avg_results

def generate_time_chart(benchmark_data):
    """Gera um gráfico de benchmark focado em métricas de tempo"""
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["Tempo de Execução (ms)"],
            "datasets": [{
                "label": "Tempo",
                "data": [benchmark_data['execution_time_ms']]
            }]
        }
    }

    # Converte o dicionário de configuração do gráfico em uma string JSON
    chart_config_json = json.dumps(chart_config)

    # Codifica a string JSON para ser usada na URL
    chart_config_encoded = requests.utils.quote(chart_config_json)

    # Constrói a URL do QuickChart.io
    chart_url = f"https://quickchart.io/chart?c={chart_config_encoded}"

    return chart_url

def generate_usage_chart(benchmark_data):
    """Gera um gráfico de benchmark focado em métricas de uso"""
    chart_config = {
        "type": "bar",
        "data": {
            "labels": ["Uso de Memória (MB)", "Uso de CPU (%)", "Uso de GPU (%)", "Temperatura GPU (°C)", "Uso de Memória GPU (MB)", "Uso de Memória do Processo (MB)"],
            "datasets": [{
                "label": "Uso",
                "data": [
                    benchmark_data['memory_usage_mb'],
                    benchmark_data['cpu_usage_percent'],
                    benchmark_data['gpu_usage_percent'] if benchmark_data['gpu_usage_percent'] is not None else 0,
                    benchmark_data['gpu_temperature'] if benchmark_data['gpu_temperature'] is not None else 0,
                    benchmark_data['gpu_memory_usage_mb'] if benchmark_data['gpu_memory_usage_mb'] is not None else 0,
                    benchmark_data['process_memory_usage_mb']
                ]
            }]
        }
    }

    # Converte o dicionário de configuração do gráfico em uma string JSON
    chart_config_json = json.dumps(chart_config)

    # Codifica a string JSON para ser usada na URL
    chart_config_encoded = requests.utils.quote(chart_config_json)

    # Constrói a URL do QuickChart.io
    chart_url = f"https://quickchart.io/chart?c={chart_config_encoded}"

    return chart_url

def main():
    """Função principal com verificação de dependências"""
    try:
        # Verificação de dependências essenciais
        import cpuinfo  # noqa: F401
        import psutil  # noqa: F401
        import GPUtil  # noqa: F401
    except ImportError as e:
        print(f"Erro: Dependência não instalada - {e.name}")
        print("Instale com: pip install py-cpuinfo psutil gputil")
        if platform.system() == 'Windows':
            print("Para recursos completos no Windows, instale também: pip install wmi")
        return

    result, benchmark_data = benchmark(repetitions=5)
    time_chart_url = generate_time_chart(benchmark_data)
    usage_chart_url = generate_usage_chart(benchmark_data)

    result['benchmark'] = benchmark_data
    result['time_chart_url'] = time_chart_url
    result['usage_chart_url'] = usage_chart_url

    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()