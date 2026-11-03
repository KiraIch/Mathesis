import Mathlib
namespace MathesisHard
def alt : ℕ → ℤ
  | 0 => 1
  | n + 1 => -alt n

theorem lean_custom_alt_sq : ∀ n : ℕ, alt n ^ 2 = 1 := by
  intro n
  induction n with
  | zero => simp [alt]
  | succ k ih => simp only [alt, neg_sq, ih]
end MathesisHard
