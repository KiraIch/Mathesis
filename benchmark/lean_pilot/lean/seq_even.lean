import Mathlib
import Mathesis.Defs
namespace MathesisPilot
theorem lean_seq_even : ∀ (n : Nat), Even (pilotSeq n) := by
  intro n
  have h : pilotSeq n = n * (n + 1) := by unfold pilotSeq; ring
  rw [h]
  exact Nat.even_mul_succ_self n
end MathesisPilot
