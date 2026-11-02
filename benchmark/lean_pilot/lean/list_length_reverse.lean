namespace MathesisPilot
theorem lean_list_length_reverse : ∀ {α : Type} (l : List α), l.reverse.length = l.length := by
  intro α
  intro l
  exact List.length_reverse
end MathesisPilot
