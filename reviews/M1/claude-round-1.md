核验范围：我读了 `faults.py`、`plant.py`、`runner.py`、`rust/src/lib.rs`、测试和 CI，没有运行任何仿真。

注入语义和 A1 一致：F1 取 onset−1 的值，F3 按 FIFO 查表，F4 按绝对 tick 降采样，F8 用 ties-even 加饱和，F5 相位连续且 2 s 前走冻结路径，F6 用 latest-wins，C32 跳号会抛 ValueError 并记为 INVALID。**M1 通过。** M2 开跑前补这 4 处：

1. `measured_run` 先写临时目录，再原子 rename。现在如果中途中断，会留下缺 `metrics.json` 的目录，续跑会直接崩溃。
2. F7 要校验 nominal 来自同一控制器、同一消融、fault=none、seed 42，并且它本身不是 INVALID。
3. 注入器拒收未注册的 onset 和 seed，F5 必须是 onset=2000。plant 里写死了 2000，传错 onset 会产生标签错误的重复 run。
4. 跨语言测试目前只覆盖最重档、seed 42、onset 200。扩到全部档位、F2/F3 的 5 个 seed、两种 base，纯注入器几秒就能跑完。F3 σ=0.5 的键名分支目前完全没测到。

另外，报告里要写明：矩阵中两个控制器都用 Python 注入器，Rust 注入器只做等价验证，留给 HIL。

```json
{"verdict":"PASS","issues":[
{"severity":"major","where":"c1/runner.py measured_run","what":"改为临时目录写入后原子 rename，避免中断后留下缺 metrics.json 的目录导致续跑崩溃","touches_frozen_or_registered":false},
{"severity":"major","where":"c1/runner.py measured_run nominal","what":"校验 F7 nominal 为同 controller、同 ablation、fault=none、seed 42，且非 INVALID","touches_frozen_or_registered":false},
{"severity":"major","where":"c1/faults.py FaultInjector.__init__; c1/plant.py","what":"拒收未注册的 onset/seed；F5 必须 onset=2000","touches_frozen_or_registered":false},
{"severity":"minor","where":"c1/tests/test_injection.py test_python_rust_binary_equivalence","what":"扩到全部档位、F2/F3 五个 seed、两种 base；覆盖 F3 σ=0.5 键名分支","touches_frozen_or_registered":false},
{"severity":"minor","where":"M4 报告","what":"写明矩阵两控制器均用 Python 注入器，Rust 注入器只做等价验证","touches_frozen_or_registered":false}]}
```
