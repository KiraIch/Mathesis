import Mathlib
namespace MathesisHard
theorem lean_set_diff_union : ∀ (α : Type) (A B : Set α), A \ B ∪ B = A ∪ B := by
  intro α A B
  ext x
  simp only [Set.mem_union, Set.mem_diff]
  tauto
end MathesisHard
