"""src/kernel/errors.py —— 全部领域异常。异常类型即条款的运行时形态，
每个异常可回溯条款号（GOV-6：无兑现的宣称是事故）。"""

class AosError(Exception):
    """AOS 领域异常基类。"""

class StoreRejection(AosError):
    """structurally-rejected：写被拒并留审计（INV-1 / KS-1.3 fail-closed / P-7 前置）。"""
class DirectWriteForbidden(StoreRejection): ...       # INV-1 / VER-28 item1
class VersionConflict(StoreRejection): ...            # KS-1.4 / VER-3
class ValidTimeViolation(StoreRejection): ...         # KS-6.1 / VER-16
class UnknownAction(StoreRejection): ...              # INV-13 / VER-27
class StreamRuleViolation(StoreRejection): ...        # KS-2.1 / INV-5 / VER-33
class UnregisteredAction(AosError): ...               # INV-1（管线层）
class StructuralRejected(AosError): ...               # KS-7.1 结构校验
class ConditionalRejected(AosError): ...              # KS-7.1 条件校验
class SnapshotUnavailable(ConditionalRejected): ...   # P-16 条件快照无法物化（条件阶段拒绝）
class SnapshotIdentityMissing(SnapshotUnavailable): ...  # 声明了身份但调用方未提供
class SnapshotEntityMissing(SnapshotUnavailable): ...    # 非创建型动作的目标实体无权威投影
class InvariantViolated(AosError): ...                # KS-1.3 写时阻断
class BudgetExceeded(AosError): ...                   # R8 fail-closed
class PrincipalRequired(AosError): ...                # KS-2.3 / INV-8
class SessionPersistFailed(AosError): ...             # 观察记录落盘失败（KS-2.2 fail-closed）
class DecisionRefIncomplete(AosError): ...            # KS-2.5 / VER-7
class InterpreterRejected(AosError): ...              # R1–R11 受限解释器
class ForbiddenPath(AosError): ...                    # INV-13 forbidden 段
class RegistrationFailed(AosError): ...               # 注册期管线 fail-closed（KS-7.2）
class GenesisFrozen(AosError): ...                    # KS-8.5（T21，可逆）
class GenesisExtinguished(AosError): ...              # KS-8.2（T22，不可逆终态）
class ReauthorizeAfterExtinguish(AosError): ...       # 基座"周界完整"的运行时形态
class ProjectionViolation(AosError): ...              # P-16 投影声明违规
class ProjectionNotMaterialized(ProjectionViolation): ...  # 投影 MUST 可重建
class PermissionDenied(AosError): ...                 # P-10 能力面 = 清单严格子集
class SagaInvalid(AosError): ...                      # P-9 编排声明非法
class UpcastingFailed(AosError): ...                  # KS-5.2 升级路径 fail-closed
