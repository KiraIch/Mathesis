import Mathlib
namespace MathesisHard
theorem lean_set_union_sub_left : ∀ (α : Type) (A B C : Set α), A ∪ B ⊆ C → A ⊆ C := by
  intro α A B C h x hx
  exact h (Set.mem_union_left B hx)
end MathesisHard
