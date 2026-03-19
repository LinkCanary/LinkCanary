import React, { useEffect, useState } from 'react';
import Card, { CardBody, CardHeader } from '../components/Card';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

const skills = ['linkcanary', 'asana', 'jira'];

export default function Integrations() {
  const [skillContents, setSkillContents] = useState({});
  const [loading, setLoading] = useState(true);
  const mcpEndpoint = `${window.location.origin}/api/mcp`;

  useEffect(() => {
    const fetchSkills = async () => {
      const contents = {};
      for (const skill of skills) {
        try {
          const res = await fetch(`/${skill}.md`);
          contents[skill] = await res.text();
        } catch (err) {
          console.error(`Failed to load ${skill}.md:`, err);
        }
      }
      setSkillContents(contents);
      setLoading(false);
    };
    fetchSkills();
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">MCP (Model Context Protocol)</h2>
          <p className="text-sm text-gray-500">
            Integrate LinkCanary with your AI agents and projects using the MCP endpoint.
          </p>
        </CardHeader>
        <CardBody className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              MCP Endpoint URL
            </label>
            <input
              type="text"
              readOnly
              value={mcpEndpoint}
              className="w-full px-3 py-2 bg-gray-100 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              onFocus={(e) => e.target.select()}
            />
          </div>
        </CardBody>
      </Card>
      
      {skills.map((skill) => (
        <Card key={skill}>
          <CardHeader>
            <h3 className="text-md font-semibold text-gray-900 mb-2 capitalize">{skill} Skill Definition</h3>
          </CardHeader>
          <CardBody>
            {loading ? (
              <div className="text-center py-8">
                <div className="animate-spin inline-block w-6 h-6 border-4 border-blue-600 border-t-transparent rounded-full" />
              </div>
            ) : (
              <div className="bg-gray-800 text-white rounded-md p-4">
                <SyntaxHighlighter language="markdown" style={atomDark}>
                  {skillContents[skill] || ''}
                </SyntaxHighlighter>
              </div>
            )}
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
