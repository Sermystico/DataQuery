import { useEffect, useState } from 'react';
import { apiClient } from '../api/client';
import type { CategoryExamples } from '../types/api';

interface ExampleChipsProps {
  onSelect: (question: string) => void;
  disabled?: boolean;
}

export function ExampleChips({ onSelect, disabled = false }: ExampleChipsProps) {
  const [categories, setCategories] = useState<CategoryExamples[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchExamples = async () => {
      try {
        const data = await apiClient.getExamples();
        if (active) {
          setCategories(data.categories || []);
        }
      } catch (err) {
        console.error('Failed to load example questions:', err);
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };

    fetchExamples();
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="examples-container">
        <div className="examples-label">Suggested Questions</div>
        <div className="chips-loading">
          <span className="chip-skeleton" />
          <span className="chip-skeleton" />
          <span className="chip-skeleton" />
        </div>
      </div>
    );
  }

  if (categories.length === 0) {
    return null;
  }

  const allExamples = categories.flatMap((cat) => cat.examples);
  const displayedExamples =
    selectedCategory === 'all'
      ? allExamples.slice(0, 8)
      : categories.find((c) => c.category === selectedCategory)?.examples || [];

  return (
    <div className="examples-container" aria-label="Example query questions">
      <div className="examples-header">
        <span className="examples-label">Example Prompts:</span>
        <div className="category-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={selectedCategory === 'all'}
            className={`tab-btn ${selectedCategory === 'all' ? 'active' : ''}`}
            onClick={() => setSelectedCategory('all')}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat.category}
              type="button"
              role="tab"
              aria-selected={selectedCategory === cat.category}
              className={`tab-btn ${selectedCategory === cat.category ? 'active' : ''}`}
              onClick={() => setSelectedCategory(cat.category)}
            >
              {cat.title}
            </button>
          ))}
        </div>
      </div>

      <div className="chips-grid">
        {displayedExamples.map((item, idx) => (
          <button
            key={`${item.title}-${idx}`}
            type="button"
            className="chip-btn"
            disabled={disabled}
            onClick={() => onSelect(item.question)}
            title={item.question}
          >
            <span className="chip-title">{item.title}</span>
            <span className="chip-arrow" aria-hidden="true">→</span>
          </button>
        ))}
      </div>
    </div>
  );
}
